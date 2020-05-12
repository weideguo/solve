#coding:utf8
import re
import uuid
from multiprocessing import Process
from traceback import format_exc

from conf import config
from .job_manager import JobManager
from lib.utils import get_host_ip
from lib.logger import logger,logger_err
from lib.wrapper import connection_error_rerun

class ProxyManager(JobManager):
    """
    作为proxy执行时的主机管理
    proxy与master的通信使用redis实现
    上传目录需要与master一致
        尚未实现，思路：
        0 web服务实现
        1 要通过rsync实时同步
        2 使用ssh命令传输
            proxy本地文件不存在时主动去master拉取
            master监听文件目录变化主动向所有proxy下发文件
    """
    
    def __init__(self,redis_config_list):
        
        super(ProxyManager, self).__init__(redis_config_list) 
        
        #优先从配置文件获取，获取失败，则使用ip地址
        try:
            self.proxy_mark = config.proxy_mark
            if not self.proxy_mark:
                raise
        except:
            self.proxy_mark = get_host_ip()
        
        self.proxy_tag="%s:%s" % (config.proxy_tag,self.proxy_mark)
        self.listen_tag=[]
        for l in config.local_ip_list:
            self.listen_tag.append(self.proxy_tag+":"+l)
        
        self.listen_tag += config.local_ip_list
        #为proxy时，在proxy本地不监听 127.0.0.1 localhost
        #监听如 proxy:AAA:10.0.0.1 10.0.0.1
        try:
            self.listen_tag.remove("127.0.0.1")
        except:
            pass
        try:
            self.listen_tag.remove("localhost")
        except:
            pass

    def __localhost(self):
        """
        proxy的本地执行
        监听 cmd_proxy:10.0.0.1:127.0.0.1  cmd_proxy:10.0.0.1:localhost
        """
        self.conn_localhost(self.listen_tag)
        
    @connection_error_rerun()
    def __remot_host(self):
        """
        符合proxy的则启动ssh连接
        """
        #init_str='proxy:10.0.0.1:192.168.16.1'
        #init_str='proxy:10.0.0.1:192.168.16.1@@@@@ba8d8c646e6711ea8d01000c295dd589'
        self.redis_init()
        while True:
            #_init=pub.parse_response(block=True)     
            _init=self.redis_send_client.blpop(self.proxy_tag)           #阻塞获取
            init_str = str(_init[-1])
            
            init_host_list=init_str.split(config.spliter)
            init_host=init_host_list[0].strip()
            if len(init_host_list)>1:
                init_host_uuid=init_host_list[1].strip()
            else:
                init_host_uuid=uuid.uuid1().hex
            
            if init_host in self.listen_tag:
                #为proxy的本地，不需要创建连接
                logger.debug("< %s > run in local mode" % init_host)
            else:
                self.conn_host(init_host,init_host_uuid,proxy_mode=True)
            

    def run_forever(self):
        """
        后台运行
        conn_localhost proxy的本地执行
        __remot_host   proxy的远程连接
        """
        self.is_listen_tag_clean(listen_tag=self.listen_tag)
        
        p_list=[]
        
        p1=Process(target=self.__localhost)
        p_list.append(p1)
        
        #远程主机众多时需要使用多进程分担，充分利用cpu
        for i in range(config.remote_process):
            p2=Process(target=self.__remot_host)
            p_list.append(p2)
            
        
        self.process_run(p_list,redis_client=self.redis_send_client)
        
        return p_list
        