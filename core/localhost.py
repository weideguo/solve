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

from conf import config



class LocalHost(AbstractHost):
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
    
        self.thread_q=Queue.Queue(t_number)   #单个主机的并发
    
    
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
    
    
    def __heart_beat(self):
        """
        心跳
        """
        while True:
            try:
                for ip_tag in self.listen_tag:
                    self.redis_send_client.set(config.prefix_heart_beat+ip_tag,time.time())
                    self.redis_send_client.expire(config.prefix_heart_beat+ip_tag,config.host_check_success_time)
            except:
                time.sleep(5)
            
            time.sleep(config.heart_beat_interval)
                
    
    def __single_run(self,cmd,cmd_uuid,ip_tag):
        try:
            #本地执行不执行扩展命令
            self.single_run(cmd,cmd_uuid,ip_tag,extend_pattern="")
        except:
            logger_err.error(format_exc())
        self.thread_q.get()

    
    def __forever_run(self,ip_tag):
        """
        无限接收命令
        """
        key = config.prefix_cmd + ip_tag
        while True:
            self.thread_q.put(1)                #控制并发数
            try:
                #使用阻塞获取 好处是能及时响应 
                t_allcmd=self.redis_send_client.blpop(key)              #redis重新连接运行会有连接报错
            except:
                try:
                    _t_allcmd=self.redis_send_client.lpop(key)
                except:
                    _t_allcmd=None
                    #logger_err.debug(format_exc())
                    time.sleep(5)
                
                t_allcmd=(_t_allcmd,_t_allcmd)   
        
            if t_allcmd:                           
                allcmd=t_allcmd[1]
                
                if allcmd:
                    allcmd=allcmd.split(config.spliter)        
                    cmd=allcmd[0].strip()
                    if len(allcmd)>1:
                        cmd_uuid=allcmd[1]
                    else:
                        cmd_uuid=uuid.uuid1().hex
                    
                    t=Thread(target=self.__single_run,args=(cmd,cmd_uuid,ip_tag))
                    t.start()
                        
                else:
                    #命令为空时释放队列
                    self.thread_q.get()
            
            else:
                #命令为空时释放队列
                self.thread_q.get()    
    
    
    #重载AbstractHost函数
    def forever_run(self):
        t1=Thread(target=self.__heart_beat)
        t_list=[t1]
        for k in self.listen_tag:
            t=Thread(target=self.__forever_run,args=(k,))
            t_list.append(t)
        
        for t in t_list:
            t.start()
        
        for t in t_list:
            t.join()
