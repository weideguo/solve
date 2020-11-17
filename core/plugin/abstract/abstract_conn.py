# -*- coding: utf-8 -*-
import time
from threading import Thread

from conf import config
from lib.utils import Singleton
from lib.redis_conn import RedisConn


def check_host_conn(host_info):
    print("if not override this function, will do nothing before conn "+str(host_info))


def preinit(func): 
    """
    初始化前进行一些操作
    """
    def my_wrapper(*args, **kargs):
        check_host_conn(args[0])
        return func(*args, **kargs)
    return my_wrapper


class AbstractConn(object):
    """
    单例模式抽象类
    """    


    def __init__(self,host_info,redis_config_list,redis_connect=None,*args,**kwargs):
        redis_send_config=redis_config_list[0]
        redis_log_config=redis_config_list[1]
    
        self.host_info = host_info
        
        if not redis_connect:
            redis_connect=RedisConn()          #使用独占连接池需要自己控制连接的释放  在此该对象的一直在使用，所以不必释放？
        
        self.redis_send_client=redis_connect.redis_init(self.redis_send_config)
        self.redis_log_client=redis_connect.redis_init(self.redis_log_config) 
        
        self.__new_forever_run()
    
    
    def __new_forever_run(self):
        """
        开启后台线程用于统一处理命令
        """        
        t1=Thread(target=self.__forever_run)
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
    
    
    def __forever_run(self):
        """
        处理方法入口
        """
        while True:
            #config.prefix_cmd="cmx_"
            if self.redis_send_client.keys(config.prefix_cmd+"*"):
                for k in self.redis_send_client.keys(config.prefix_cmd+"*"):
                    cmd = self.redis_send_client.lpop(k)
                    ip = k.split(config.prefix_cmd)[1]
                    #self.single_exe(ip,cmd)
                    t=Thread(target=self.single_exe,args=(ip,cmd))
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


    def forever_run(self):
        """
        在单例模式中 提供给上层的调用应该为空
        """
        pass
    
