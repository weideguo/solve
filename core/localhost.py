# -*- coding: utf-8 -*-
import os
import re
import uuid
import time
import shutil
import sys
from threading import Thread
import subprocess
from traceback import format_exc

from lib.wrapper import gen_background_log_set,connection_error_rerun,command_fliter,logger,logger_err
from lib.utils import get_host_ip
from lib.redis_conn import RedisConn
from lib.compat import Queue

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
    def exe_cmd(self,cmd,background_log_set=None,*arg,**kwargs):
        
        p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
        
        if re.match(".*&$",cmd.strip()):
            #执行的命令为后台执行时
            #后台执行获取不了stdout stderr exit_code，在此构建一个虚假值
            return "you should check if this process has executed correctly","",0
        
        if background_log_set:
            stdout,stderr = background_log_set(p.stdout,p.stderr)
        else:
            stdout = p.stdout.read()
            stderr = p.stderr.read()
            try:
                # python2 b"" -> u""
                stdout = stdout.decode("utf8")
                stderr = stderr.decode("utf8")
            except:
                pass
                 
        p.communicate()
        exit_code=p.returncode

        return stdout, stderr, exit_code    
    
    #重载AbstractHost函数
    def save_file(self,filename,content,mode="w",*arg,**kwargs):
        path=os.path.dirname(filename)
        os.makedirs(path,exist_ok=True) 
        if os.path.isdir(filename):
            raise Exception("filename is a dir")
        
        if os.path.isfile(filename):
            shutil.move(filename, filename+"_"+str(time.time()))
        
        with open(filename,mode) as f:
            f.write(content)
            
                        
    #重载AbstractThread的函数        
    def real_func(self,cmd,cmd_uuid,ip_tag,*args,**kwargs):
        if cmd:
            # 本地执行只实现部分扩展命令
            self.single_run(cmd,cmd_uuid,ip_tag,extend_pattern=".*__save__.*")            
            
                  
    #重载AbstractHost函数        
    def forever_run(self):
        t1=Thread(target=self.heart_beat,args=(None,config.host_check_success_time*3,False))
        self.thread_list.append(t1)
        self.serve_forever()           
            
      
