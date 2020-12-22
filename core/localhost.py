# -*- coding: utf-8 -*-
import uuid
import time
import sys
if sys.version_info>(3,0):
    import queue as Queue
else:
    import Queue
from threading import Thread
import subprocess
from traceback import format_exc

from lib.wrapper import gen_background_log_set,connection_error_rerun,command_fliter,logger,logger_err
from lib.utils import get_host_ip
from lib.redis_conn import RedisConn

from core.abstract.abstract_host import AbstractHost
from core.abstract.parallel import AbstractThread

from conf import config



class LocalHost(AbstractHost,AbstractThread):
    """
    对本地的执行
    """
    def __init__(self,redis_config_list,listen_tag,t_number=config.max_localhost_thread,redis_connect=None):        
        self.redis_send_config=redis_config_list[0]
        self.redis_log_config=redis_config_list[1]
          
        if redis_connect:                                                                            
            self.redis_connect=redis_connect                                                       #单个进程所创建的远程连接共享连接池                               
            self.is_disconnect=False                                                               #关闭远程连接不能回收redis连接
        else:                                                                                      
            self.redis_connect=RedisConn(max_connections=config.localhost_redis_pool_size)         #每个远程连接使用自己的连接池
            self.is_disconnect=True                                                                #在关闭远程连接时回收redis连接
        
        self.redis_refresh()
        
        self.listen_tag=listen_tag
        
        self.run_flag=True
        self.thread_list=[]
        self.parallel_list=listen_tag
        
        self.init_parallel(t_number,stop_able=False,join=True)     #即使线程运行错误 也继续运行

    
    def redis_refresh(self):
        self.redis_send_client=self.redis_connect.refresh(self.redis_send_config,force=True)
        self.redis_log_client=self.redis_connect.refresh(self.redis_log_config,force=True)
    
    
    #重载AbstractHost函数
    def exe_cmd(self,cmd,background_log_set,ip_tag):
        p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
                
        stdout,stderr = background_log_set(p.stdout,p.stderr)
                    
        p.communicate()
        exit_code=p.returncode

        return stdout, stderr, exit_code    
    
                        
    #重载AbstractThread的函数        
    def real_func(self,cmd,cmd_uuid,ip_tag,*args,**kwargs):
        if cmd:
            self.single_run(cmd,cmd_uuid,ip_tag,extend_pattern="")            
            
                  
    #重载AbstractHost函数        
    def forever_run(self):
        t1=Thread(target=self.heart_beat)
        self.thread_list.append(t1)
        self.serve_forever()           
            
      
