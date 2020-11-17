# -*- coding: utf-8 -*-
#一些函数的封装
import os
import time
import threading
from threading import Thread
from traceback import format_exc

from redis.exceptions import ConnectionError

from .logger import logger_err


def gen_background_log_set(cmd_uuid,redis_client,len=0,retry=60,interval=1):
    """生成执行命令时设置日志的函数"""
    def background_log_set(stdout, stderr):
        def update_log(out,tag):
            """真实用于设置日志的后台函数"""
            new_log=None    #未写入redis的日志
            while True:
                #单行读取，读取不到阻塞，但读取结束后不会阻塞
                #readline(1) read(1) 作用类似，只获取一个字符，但更新太频繁，消耗太大，在其他更高实时性场景使用
                if len:
                    __new_log=out.readline(len)
                else:
                    __new_log=out.readline()
                
                if new_log:
                    new_log=new_log+__new_log
                else:
                    new_log=__new_log
                    
                ###readline可能值                    
                # new_log=u"中公文\n"         #ssh执行
                # new_log=b"\xe4\xb8\xad1\n"  #本地执行
                #
                # new_log=b"\xe4"  #单字节可能需要先拼接后再转换
                               
                #_log=u""
                
                def set_new_log(new_log):
                    try:
                        _log=redis_client.hget(cmd_uuid,tag) or ""
                    except:
                        #获取先前的日志失败 则先缓存
                        return new_log
                    
                    _log_all=_log
                    try:     
                        _log_all = _log+new_log
                    except:                
                        try:
                            #b"" -> u""
                            #单字节可能需要先拼接后再转换
                            _log_all = _log+new_log.decode("utf8")                        
                        except:
                            pass
                    
                    if _log_all != _log:
                        try:
                            redis_client.hset(cmd_uuid,tag, _log_all)
                            new_log=None
                        except:
                            #写日志时redis连接存在问题 则未写入redis的日志增长
                            pass
                    return new_log
                
                # 单行读取，每一行至少为"\n"
                if not __new_log:
                    r=0
                    while new_log:
                        #尝试一段时间 都失败再报错 redis sentinel 默认30s恢复
                        time.sleep(interval)
                        r+=1
                        new_log=set_new_log(new_log)
                        if r>retry:
                            raise Exception("can not write log to redis: ", new_log)
                    break
                
                new_log=set_new_log(new_log)
                
        
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



def connection_error_rerun(interval=5):
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
                #except:
                    logger_err.debug(format_exc())
                    time.sleep(interval)
                    if args:
                        func_name="%s.%s" % (args[0].__class__.__name__, func.__name__)
                    else:
                        func_name=func.__name__
                    
                    logger_err.info("function:%s  retry" % func_name)
                          
        return __wrapper2
    return __wrapper
    
    
    
def retry_wrap(f,error_class=BaseException,interval=5,retry=0,err_return=None,err_func=None):
    """
    运行函数错误出现错误时重新执行
    """
    def _wrap(*args,**kwargs):
        r=None
        _retry=0
        while True:
            try:
                r=f(*args,**kwargs)
                break
            except error_class:
                #print(f.__name__ +"\n"+ format_exc())
                logger_err.debug(f.__name__ +"\n"+ format_exc())
                if interval and ((not retry) or _retry< retry):
                    _retry += 1
                    #print("function %s retry %d" % (f.__name__,_retry))
                    logger_err.debug("PID %d ThreadID %d function %s retry %d" % (os.getpid(), threading.currentThread().ident ,f.__name__,_retry))
                    time.sleep(interval)
                else:
                    r=err_return
                    if err_func:
                        err_func(*args,**kwargs)
                    break
                
        return r
    return _wrap


class RerunableThread(threading.Thread):
    """发生错误导致异常推出后可以重复执行的线程"""
    def __init__(self, interval=5, target=None, *args,**kwargs):
        threading.Thread.__init__(self)
        self.interval = interval
        self.target = target
        self.args = args
        self.kwargs = kwargs
    
    
    def run(self):
        try:
            self.target(*self.args,**self.kwargs)
        except:
            #print(format_exc())
            logger_err.debug(format_exc())
            time.sleep(self.interval)
            self.run()
    
    