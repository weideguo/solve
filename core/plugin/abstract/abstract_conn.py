#coding:utf8
import time
import redis
from threading import Thread

from conf import config
from lib.utils import Singleton


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


class AbstractConn():
    """
    单例模式抽象类
    """    


    def __init__(self,host_info,redis_send_pool,redis_log_pool):
        self.redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)
        self.redis_log_client=redis.StrictRedis(connection_pool=redis_log_pool)
        self.__new_forever_run()
        print("init")


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
            config.prefix_cmd="cmx_"
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
    
