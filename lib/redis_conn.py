# -*- coding: utf-8 -*-
import redis
from redis import BlockingConnectionPool
from redis.sentinel import Sentinel

from threading import Lock 


class RedisConn(object):
    """        
    BlockingConnectionPool
    线程间通过阻塞复用连接 
    进程间也可以通过阻塞复用
    """
    
    def __init__(self,decode_responses=True,encoding_errors="ignore",retry_on_timeout=True,timeout=None,max_connections=5 ):
        self.timeout=          timeout                     #等待获取可用连接的时间 None一直等待
        self.max_connections=  max_connections             #最大连接数
        
        self.decode_responses= decode_responses            #将结果自动编码为unicode格式，否则对于python3结果格式为 b"xxx"
        self.encoding_errors = encoding_errors             #decode的选项，编码出错时的处理方式，可选 strict ignore replace 默认为strict 
        self.retry_on_timeout= retry_on_timeout            #执行命令时出现超时继续尝试
        
        self.conn_list=[]
        
        self.lock = Lock()
        
    
    def init_single(self, host, port, db, password):
        """
        单个服务模式
        """
        redis_pool=BlockingConnectionPool(host=host, port=port, db=db, password=password,\
                   decode_responses=self.decode_responses, encoding_errors=self.encoding_errors,\
                   retry_on_timeout=self.retry_on_timeout, max_connections=self.max_connections, timeout=self.timeout)
        
        redis_client=redis.StrictRedis(connection_pool=redis_pool)
        return redis_client
    
    
    def init_sentinel(self, sentinels, service_name, db, password, is_master=True):
        """
        哨兵模式
        """
        sentinel = Sentinel(sentinels)
        if is_master:
            client = sentinel.master_for(service_name, password=password, db=db,\
                     decode_responses=self.decode_responses, encoding_errors=self.encoding_errors,retry_on_timeout=self.retry_on_timeout,\
                     max_connections=self.max_connections, socket_timeout=self.timeout)
        else:
            client = sentinel.slave_for(service_name, password=password, db=db, \
                     decode_responses=self.decode_responses, encoding_errors=self.encoding_errors,retry_on_timeout=self.retry_on_timeout,\
                     max_connections=self.max_connections, socket_timeout=self.timeout)
        
        return client

    def init_cluster(self, nodes, password):
        """
        cluster模式
        """
        # from redis.cluster import RedisCluster,ClusterNode
        # cluster_nodes = [ ClusterNode(n[0],n[1]) for n in nodes]
        # client = RedisCluster(startup_nodes=cluster_nodes, password=password,\
        #          decode_responses=self.decode_responses, encoding_errors=self.encoding_errors,\
        #          retry_on_timeout=self.retry_on_timeout, max_connections=self.max_connections, timeout=self.timeout)
        # return client
        raise Exception("not support redis cluster yet %s" % nodes)

        
    def init(self, redis_config):
        """
        #redis_config
        {
            "db": 0,
            "password": "my_redis_passwd",
            #"service_name": "mymaster",                                                          #是否使用sentinel
            "nodes": [('127.0.0.1', 26479)],
            #"nodes": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)],       
        }
        """
        with self.lock:
            #可以允许多个线程同时发起创建命令
            for conf,conn in self.conn_list:
                if redis_config == conf:
                    return conn
            
            password=redis_config["password"]
            db=redis_config["db"]
            
            is_sentinel=False
            if len(redis_config["nodes"]) == 0:
                raise Exception("redis nodes must not empty %s" % redis_config)

            if "service_name" in redis_config and redis_config["service_name"]:
                sentinels = redis_config["nodes"]
                service_name = redis_config["service_name"]
                if sentinels and service_name:
                    is_sentinel = True
            
            if is_sentinel:
                redis_client = self.init_sentinel(sentinels, service_name, db, password)  
            elif len(redis_config["nodes"]) == 1:
                host = redis_config["nodes"][0][0]
                port = redis_config["nodes"][0][1]
                redis_client = self.init_single(host, port, db, password)
            else:
                # cluster只能使用db0
                redis_client = self.init_cluster(redis_config["nodes"], password)
            
            self.conn_list.append((redis_config,redis_client))
        
            return redis_client   
    

    def refresh(self, redis_config, force=False, connect_client=None):
        """
        如果发生断开，重新获取客户端
        使用连接池没有重连的必要，客户端自动重连
        多进程可能需要自己刷新 
        """
        if connect_client:
            try:
                connect_client.ping()
            except:
                connect_client=self.redis_init(redis_config)
        
            return connect_client    
            
        
        redis_client_pair=None
        for conf,conn in self.conn_list:
            if redis_config == conf:
                redis_client_pair=(conf,conn)
        
        if redis_client_pair:
            if force:
                self.conn_list.remove(redis_client_pair)
            else:
                try:
                    redis_client_pair[1].ping()
                    return redis_client_pair[1]
                except:
                    #from traceback import format_exc
                    #print(format_exc())
                    self.conn_list.remove(redis_client_pair)

        return self.init(redis_config)
        
