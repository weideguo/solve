#coding:utf8

import redis

from conf import config

from .job_manager import JobManager
from .job_manager import RemoteHost
from .localhost import LocalHost



class ProxyManager(JobManager):
    """
    作为proxy执行时的主机管理
    proxy与master的通信使用redis实现
    与master使用的文件目录（playbook、上传目录）要通过rsync实时同步，且存放位置一致
    """
    
    def __init__(self,redis_send_pool,redis_log_pool,redis_tmp_pool,redis_job_pool,redis_config_pool):
        """
        self.redis_send_pool=redis_send_pool
        self.redis_log_pool=redis_log_pool
        self.redis_tmp_pool=redis_tmp_pool
        self.redis_job_pool=redis_job_pool        
        self.redis_config_pool=redis_config_pool
        
        
        self.redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)    
        self.redis_log_client=redis.StrictRedis(connection_pool=redis_log_pool)
        self.redis_job_client=redis.StrictRedis(connection_pool=redis_job_pool)
        self.redis_tmp_client=redis.StrictRedis(connection_pool=redis_tmp_pool)
        self.redis_config_client=redis.StrictRedis(connection_pool=redis_config_pool)
        """
        super(ProxyManager, self).__init__(redis_send_pool,redis_log_pool,redis_tmp_pool,redis_job_pool,redis_config_pool))   
        

        self.proxy_tag="PROXY:"+get_host_ip()


    def __localhost(self,listen_key)
        """
        proxy的本地执行
        监听 cmd_proxy:10.0.0.1:127.0.0.1  cmd_proxy:10.0.0.1:localhost
        """
        
        
    
    def __remot_host():
        """
        符合proxy的则启动host
        """
        #init_host要通过接受广播获取，因为同时存在很多个proxy
        #init_str='proxy:10.0.0.1:192.168.16.1'
        
        pub=self.redis_send_client.pubsub()
        pub.psubscribe(config.proxy_tag)
        
        while True:
            init_str=pub.parse_response(block=True)     #阻塞获取
            print(init_str)
            
        """
        init_str='proxy:10.0.0.1:192.168.16.1@@@@@ba8d8c646e6711ea8d01000c295dd589'
        init_host_list=init_str.split(config.spliter)
        init_host=init_host_list[0].strip()
        if len(init_host_list)>1:
            init_host_uuid=init_host_list[1].strip()
        else:
            init_host_uuid=uuid.uuid1().hex
        
        #在redis中存储为 realhost_proxy:proxy_ip:remote_ip
        host_info=self.redis_config_client.hgetall(config.prefix_realhost+init_host)
        host_info["ip"]=init_host.split(":")[2]            #proxy:proxy_ip:remote_ip
        host_info["tag"]=init_host   
        if host_info["ip"] in config.local_ip_list:
            #在proxy的本地执行，不需要创建连接
            logger.debug("< %s > run in local mode" % init_host)
        else:
            self.conn_host(init_host,init_host_uuid)
        """

    def run_forever(self):
        """
        后台运行
        proxy只用于管理主机的连接
        """
        t1=Thread(target=self.__remot_host)
        t1.start()
    
    