# -*- coding: utf-8 -*-
import os
import re
import uuid
import time
import sys
if sys.version_info>(3,0):
    import queue as Queue
else:
    import Queue
from threading import Thread
from traceback import format_exc

from lib.redis_conn import RedisConn
from lib.wrapper import logger,logger_err
from lib.myssh import MySSH
from lib.password import Password

from core.abstract.abstract_host import AbstractHost
from core.abstract.parallel import AbstractThread

from conf import config


password=Password(aes_key=config.aes_key)


class RemoteHost(MySSH, AbstractHost, AbstractThread):
    """
    SSH远程连接类
    在远端执行命令 上传下载文件
    持续监听队列获取命令
    续监听队列判断是否关闭连接
    
    只确保当前正在执行的能正确返回 不必维护执行队列
    """
    
    def __init__(self,host_info,redis_config_list,t_number=config.max_concurrent_thread,redis_connect=None):
        
        host_info["passwd"] = password.decrypt(str(host_info.get("passwd","")))
        
        super(RemoteHost, self).__init__(host_info)       
        
        self.ip =host_info["ip"]
        self.ip_tag=host_info.get("tag") or self.ip
        #self.host_uuid=host_info["uuid"]   #使用uuid可以更精确控制单个主机 当一个ip存在多个连接时
        
        self.cmd_key       = config.prefix_cmd+self.ip_tag
        self.heartbeat_key = config.prefix_heart_beat+self.ip_tag
        self.cloing_key    = config.prefix_closing+self.ip_tag
        
        self.redis_send_config=redis_config_list[0]
        self.redis_log_config=redis_config_list[1]
        
        if redis_connect:
            rc=redis_connect                                                        #单个进程所创建的远程连接共享连接池  redis连接被多个远程连接复用
            self.is_disconnect=False                                                #关闭远程连接不能回收redis连接
        else:
            rc=RedisConn(max_connections=config.remote_host_redis_pool_size)        #每个远程连接使用自己的连接池  有些连接不能被共享  如进行blpop操作时/消息订阅时 因而在此需要大于2
            self.is_disconnect=True                                                 #在关闭远程连接时回收redis连接

        self.redis_send_client=rc.refresh(self.redis_send_config)
        self.redis_log_client=rc.refresh(self.redis_log_config) 
        
        self.redis_client_list=[self.redis_send_client,self.redis_log_client]
        
        self.run_flag=False
        self.thread_list=[]
        self.parallel_list=[self.ip_tag]
        self.init_parallel(t_number)
    
       
    def init_conn(self):
        """
        初始化连接
        """
        super(RemoteHost, self).init_conn()
        
        self.run_flag=True
    
    
    #重载AbstractThread的函数
    def real_func(self,cmd,cmd_uuid,ip_tag,*args,**kwargs):
        if cmd:
            self.single_run(cmd,cmd_uuid,ip_tag) 
        
    
    #重载AbstractHost提供给上层的入口函数
    def forever_run(self):
        try:
            self.init_conn()
        except BaseException:
            logger_err.error(format_exc())
            raise BaseException
        else:
            t1=Thread(target=self.heart_beat,args=(logger.debug,))
            t2=Thread(target=self.close_conn)
            self.thread_list.append(t1)
            self.thread_list.append(t2)
            self.serve_forever()
        
