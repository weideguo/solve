# -*- coding: utf-8 -*-
import time
import uuid
import sys
#if sys.version_info>(3,0):
#    import queue as Queue
#else:
#    import Queue
import threading
from threading import Thread

from lib.utils import Singleton
from lib.redis_conn import RedisConn
from lib.wrapper import logger,logger_err,command_split
from lib.compat import Queue

from conf import config

def check_host_conn(*args, **kargs):
    print("if not override this function, will do nothing before conn")


def preinit(func): 
    """
    初始化前进行一些操作
    """
    def my_wrapper(*args, **kargs):
        check_host_conn(*args, **kargs)
        return func(*args, **kargs)
    return my_wrapper


class AbstractConn(object):
    """
    单例模式抽象类
    """    

    def init(self,redis_config_list,redis_connect=None,*args,**kwargs):
        self.redis_send_config=redis_config_list[0]
        self.redis_log_config=redis_config_list[1]
        
        if not redis_connect:
            redis_connect=RedisConn()      
        
        self.redis_send_client=redis_connect.refresh(self.redis_send_config)
        self.redis_log_client=redis_connect.refresh(self.redis_log_config) 
        
        #self.thread_q=Queue.Queue(config.max_concurrent_thread)         #控制线程生成 
        
        self.thread_q=Queue.Queue(config.max_concurrent_all)
        self.host_queue_info={}      #控制单个主机的并发
        
        self.__forever_run()
    
    
    def __forever_run(self):
        """
        开启后台线程用于统一处理命令
        """        
        t1=Thread(target=self._forever_run)
        t2=Thread(target=self.__conn_manage)
        t1.start()
        t2.start()


    def single_exe(self,cmd,cmd_uuid,ip_tag):
        """
        用于执行单条命令的函数
        必须重写
        """
        print(cmd,cmd_uuid,ip_tag)
        raise Exception('.single_exe() must be overridden')
    
    
    def __single_exe(self,cmd,cmd_uuid,ip_tag):
        """
        命令执行线程控制
        """
        try:
            if not self.host_queue_info.get(ip_tag):
                self.host_queue_info[ip_tag]=Queue.Queue(config.max_concurrent_thread) 
            if not self.host_queue_info[ip_tag].full():
                self.host_queue_info[ip_tag].put(1)
                self.single_exe(cmd,cmd_uuid,ip_tag)
                self.host_queue_info[ip_tag].get()
            else:
                #单个主机的并发达到上限
                self.redis_send_client.rpush(config.prefix_cmd+ip_tag, cmd+config.spliter+cmd_uuid)
                time.sleep(0.1)
        except:
            logger_err.debug(format_exc())

        self.thread_q.get(block=False) 
    
    
    def _forever_run(self):
        """
        处理方法入口  
        如需要增加线程控制 重载实现
        """
        while True:
            #是否应该考虑跟配置的信息对比，只有特定的才监听？用于混合多种连接方式存在时？
            if list(self.redis_send_client.scan_iter(config.prefix_cmd+"*")):
                for k in self.redis_send_client.scan_iter(config.prefix_cmd+"*"):
                    self.thread_q.put(1)
                    allcmd = self.redis_send_client.lpop(k)
                    if allcmd:
                        ip_tag = k.split(config.prefix_cmd)[1]
                        
                        cmd,cmd_uuid=command_split(allcmd,config.spliter,config.uuid_len)
                        
                        t=Thread(target=self.__single_exe,args=(cmd,cmd_uuid,ip_tag))
                        t.start()
                    else:
                        self.thread_q.get(block=False) 
            else:
                #为空时控制频率  
                time.sleep(1) 
    

    def conn_manage(self):
        """
        单次状态管理
        """
        pass
    
        
    def __conn_manage(self):
        """
        用于管理连接状态
        """
        while True:
            self.conn_manage()  
            time.sleep(config.heart_beat_interval)



    
