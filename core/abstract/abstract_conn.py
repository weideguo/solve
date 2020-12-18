# -*- coding: utf-8 -*-
import time
from threading import Thread

from lib.utils import Singleton
from lib.redis_conn import RedisConn

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
        
        self.__new_forever_run()
    
    
    def __new_forever_run(self):
        """
        开启后台线程用于统一处理命令
        """        
        t1=Thread(target=self._forever_run)
        t2=Thread(target=self.__conn_manage)
        t1.start()
        t2.start()


    def single_exe(self,ip,cmd):
        """
        用于执行单条命令的函数
        必须重写
        """
        print(ip,cmd)
        raise Exception('.single_exe() must be overridden')
    
    
    def _forever_run(self):
        """
        处理方法入口  
        如需要增加线程控制 重载实现
        """
        while True:
            #config.prefix_cmd="cmx_"
            if self.redis_send_client.keys(config.prefix_cmd+"*"):
                for k in self.redis_send_client.keys(config.prefix_cmd+"*"):
                    cmd = self.redis_send_client.lpop(k)
                    ip_tag = k.split(config.prefix_cmd)[1]
                    #self.single_exe(ip,cmd)
                    t=Thread(target=self.single_exe,args=(ip_tag,cmd))
                    t.start()
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



    
