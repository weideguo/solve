# -*- coding: utf-8 -*-
#一些函数的封装
import os
import time
from threading import Thread
from traceback import format_exc

from redis.exceptions import ConnectionError

from .logger import logger_err
from .utils import trans
from conf import config


domain="solve"
relate_path = "./locale/"
locale_path= os.path.join(config.base_dir, relate_path)

if hasattr(config,"language"):
    language_setting=config.language
else:
    language_setting=""

_=trans(domain, locale_path, language_setting)



def gen_background_log_set(cmd_uuid,redis_client,len=0):
    """生成执行命令时设置日志的函数"""
    def background_log_set(stdout, stderr):
        def update_log(out,tag):
            """真实用于设置日志的后台函数"""
            #防止获取到None
            redis_client.hset(cmd_uuid,tag,"")
            while True:
                #单行读取，读取不到阻塞，但读取结束后不会阻塞
                #readline(1) read(1) 作用类似，只获取一个字符，但更新太频繁，消耗太大，在其他更高实时性场景使用
                if len:
                    new_log=out.readline(len)
                else:
                    new_log=out.readline()
                try:
                    new_log=str(new_log,encoding="utf8")
                except:
                    pass
                old_log=redis_client.hget(cmd_uuid,tag)
                redis_client.hset(cmd_uuid,tag,old_log+new_log)
                # 单行读取，每一行至少为"\n"
                if not new_log:
                    break
                
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
            sout,serr = "",_("redis conn error, check if execute success manully")
        
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