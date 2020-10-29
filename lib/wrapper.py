# -*- coding: utf-8 -*-
#一些函数的封装
import time
from threading import Thread
from traceback import format_exc

from redis.exceptions import ConnectionError

from .logger import logger_err


def gen_background_log_set(cmd_uuid,redis_client,len=0):
    """生成执行命令时设置日志的函数"""
    def background_log_set(stdout, stderr):
        def update_log(out,tag):
            """真实用于设置日志的后台函数"""
            #防止获取到None
            redis_client.hset(cmd_uuid,tag,"")
            _new_log=b""
            while True:
                #单行读取，读取不到阻塞，但读取结束后不会阻塞
                #readline(1) read(1) 作用类似，只获取一个字符，但更新太频繁，消耗太大，在其他更高实时性场景使用
                if len:
                    new_log=out.readline(len)
                else:
                    new_log=out.readline()
                
                # 单行读取，每一行至少为"\n"
                if not new_log:
                    if _new_log:
                        raise Exception("can not decode to unicode", _new_log)
                    break
                   
                ###可能值                    
                # new_log=u"中公文\n"         #ssh执行
                # new_log=b"\xe4\xb8\xad1\n"  #本地执行
                #
                # new_log=b"\xe4"  #单字节可能需要先拼接后再转换
                               
                #_log=u""
                _log=redis_client.hget(cmd_uuid,tag) 
                _log_all=_log
                try:     
                    _log_all = _log+new_log
                except:
                    #new_log=b""
                    #单字节可能需要先拼接后再转换
                    _new_log=_new_log+new_log
                    try:
                        #b"" -> u""
                        _log_all = _log+_new_log.decode("utf8")
                        #_log_all = _log+str(new_log,encoding="utf8")  #python2 not support
                        _new_log=b""
                    except:
                        pass
                
                if _log_all != _log:
                    redis_client.hset(cmd_uuid,tag, _log_all)
                
                #time.sleep(1)
        
        #需要开线程同时处理stdout stderr            
        t1=Thread(target=update_log,args=(stdout,"stdout"))
        t2=Thread(target=update_log,args=(stderr,"stderr"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        try:
            sout=redis_client.hget(cmd_uuid,"stdout")
            serr=redis_client.hget(cmd_uuid,"stderr")
        except:
            sout,serr = "","redis conn error, check if execute success manully"
        
        #如果线程运行失败，处理None
        if not sout:
            sout = ""
        if not serr:
            serr = ""
        return sout,serr
        
    return background_log_set



def connection_error_rerun(retry_gap=5):
    """
    当发生连接错误时函数的重新运行
    """
    def __wrapper(func):                  
        def __wrapper2(*args, **kwargs):
            while True:
                try:
                    func(*args, **kwargs)
                    break
                except ConnectionError:
                    logger_err.debug(format_exc())
                    time.sleep(retry_gap)
                    if args:
                        func_name="%s.%s" % (args[0].__class__.__name__, func.__name__)
                    else:
                        func_name=func.__name__
                    
                    logger_err.info("function:%s  retry" % func_name)
                          
        return __wrapper2
    return __wrapper