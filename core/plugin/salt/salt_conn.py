#encoding:utf8
from lib.utils import Singleton
from ..abstract import abstract_conn
from ..abstract.abstract_conn import AbstractConn


def check_host_conn(host_info):
    print("will do something "+str(host_info))

abstract_conn.check_host_conn=check_host_conn

@abstract_conn.preinit
@Singleton
class SaltConn(AbstractConn):
    """
    使用salt分发命令
    """    

    
    def single_exe(self,ip,cmd):
        """
        单次命令的执行 
        可以为阻塞式实行，即可以等执行完毕并获取到结果
        """
        print("execute by salt %s %s" % (ip,cmd))



    def conn_manage(self):
        """ 
        单次连接状态管理
        用于刷新heart_beat
        """
        print("get conn info once")
    
