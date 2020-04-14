#coding:utf8
import redis
from redis.sentinel import Sentinel

class RedisConn(object):
    
    decode_responses=True      #将结果自动编码为unicode格式，否则对于python3结果格式为 b"xxx"
    encoding_errors="ignore"   #decode的选项，编码出错时的处理方式，可选 strict ignore replace 默认为strict 
    
    def redis_init_single(self, host, port, db, password):
        """
        单个服务模式
        """
        redis_pool=redis.ConnectionPool(host=host, port=port, db=db, password=password,\
                                        decode_responses=self.decode_responses,encoding_errors=self.encoding_errors)
        
        redis_client=redis.StrictRedis(connection_pool=redis_pool)
        return redis_client
    
    
    def redis_init_sentinel(self, sentinels, service_name, db, password, is_master=True):
        """
        哨兵模式
        """
        sentinel = Sentinel(sentinels)
        if is_master:
            client = sentinel.master_for(service_name, password=password, db=db,\
                                        decode_responses=self.decode_responses, encoding_errors=self.encoding_errors)
        else:
            client = sentinel.slave_for(service_name, password=password, db=db, \
                                        decode_responses=self.decode_responses, encoding_errors=self.encoding_errors)
        
        return client
        
        
    def redis_init(self, redis_config):
        """
        #redis_config
        {
            "db": 0,
            "password": "my_redis_passwd",
            "host": "127.0.0.1",                                                                  #使用sentinel则这个不必设置
            "port": 6379,                                                                         #使用sentinel则这个不必设置
            #"service_name": "mymaster",                                                          #是否使用sentinel
            #"sentinels": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)],       #是否使用sentinel
        }
        """
        password=redis_config["password"]
        db=redis_config["db"]
        
        is_sentinel=False
        if "sentinels" in redis_config and "service_name" in redis_config:
            sentinels=redis_config["sentinels"]
            service_name=redis_config["service_name"]
            if sentinels and service_name:
                is_sentinel=True
        
        if is_sentinel:
            redis_client=self.redis_init_sentinel(sentinels,service_name, db, password)  
        else:
            host=redis_config["host"]
            port=redis_config["port"]
            redis_client=self.redis_init_single(host, port, db, password)
        
        return redis_client   
        