# -*- coding: utf-8 -*-
import re
import uuid
from multiprocessing import Process
from traceback import format_exc

from conf import config
from .base_manager import BaseManager
from lib.utils import get_host_ip
from lib.wrapper import connection_error_rerun,logger,logger_err
from lib.redis_conn import RedisConn


class ProxyManager(BaseManager):
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
    
    def __init__(self, redis_connect, redis_config_list):
        
        super(ProxyManager, self).__init__(redis_connect,redis_config_list) 
        
        #优先从配置文件获取，获取失败，则使用ip地址
        self.proxy_mark = getattr(config,"proxy_mark","") or get_host_ip()
        
        self.proxy_tag = "%s:%s" % (config.proxy_tag,self.proxy_mark)
        
        #为proxy时 在proxy本地不监听 127.0.0.1 localhost 防止跟master的发生冲突
        self.listen_tag = [ ip for ip in listen_tag if ip not in ["127.0.0.1","localhost"] ]
        
    
    @connection_error_rerun()
    def __remot_host(self):
        """
        符合proxy的则启动ssh连接
        """
        #init_str='192.168.16.1'
        #init_str='192.168.16.1_aaa'
        #init_str='192.168.16.1@@@@@ba8d8c646e6711ea8d01000c295dd589'
        #redis_connect=RedisConn()
        redis_connect=None
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
            
            self.conn_host(init_host,redis_connect,init_host_uuid)    
            
            
    def run_forever(self):
        """
        后台运行
        localhost      proxy的本地执行
        __remot_host   proxy的远程连接
        """
        #self.is_listen_tag_clean(listen_tag=self.listen_tag)
        self.is_listen_tag_clean()
        
        p_list=[]
        
        #p1=Process(target=self.localhost,args=(self.listen_tag,))
        p1=Process(target=self.localhost)
        p_list.append(p1)
        
        #远程主机众多时需要使用多进程分担，充分利用cpu
        for i in range(config.remote_process):
            p2=Process(target=self.__remot_host)
            p_list.append(p2)
            
        
        self.process_run(p_list,redis_client=self.redis_send_client)
        
        return p_list
        