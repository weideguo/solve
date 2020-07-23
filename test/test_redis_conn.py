# -*- coding: utf-8 -*-
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.redis_conn import RedisConn


if __name__ == "__main__":
    rc=RedisConn()
    
    redis_send={
        "db": 0,
        "password": "my_redis_passwd",
        "host": "127.0.0.1",                                                                  #使用sentinel则这个不必设置
        "port": 6379,                                                                         #使用sentinel则这个不必设置
        #"service_name": "mymaster",                                                          #是否使用sentinel
        #"sentinels": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)],       #是否使用sentinel
    }
    
    redis_send_client=rc.redis_init(redis_send)
    
    redis_send_client.info()
    
    redis_send_client=rc.refresh(redis_send_client,redis_send)
    
    redis_send_client=rc.refresh(None,redis_send)
    
    sentinels=redis_send["sentinels"]
    service_name=redis_send["service_name"]
    db=redis_send["db"]
    password=redis_send["password"]
    redis_slave_client=rc.redis_init_sentinel(sentinels, service_name, db, password, is_master=False)
    
    
    