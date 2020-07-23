# -*- coding: utf-8 -*-
import os
import sys
import redis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.proxy_manager import ProxyManager



if __name__=="__main__":
    """
    #redis_config
    {
        "db": 0,
        "password": "my_redis_passwd",
        "host": "127.0.0.1",         
        "port": 6379,                
        "service_name": "mymaster",                                                         
        "sentinels": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)]      
    }
    """
    #可清除以下
    redis_send_config={"host":"127.0.0.1", "port":6379, "db":0, "password":"my_redis_passwd"}
    redis_log_config={"host":"127.0.0.1", "port":6379, "db":1, "password":"my_redis_passwd"}
    redis_tmp_config={"host":"127.0.0.1", "port":6379, "db":2, "password":"my_redis_passwd"}
    #不可清除以下
    redis_job_config={"host":"127.0.0.1", "port":6379, "db":14, "password":"my_redis_passwd"}
    redis_config_config={"host":"127.0.0.1", "port":6379, "db":15, "password":"my_redis_passwd"}
    
    
    pm=ProxyManager([redis_send_config,redis_log_config,redis_tmp_config,redis_job_config,redis_config_config])
    pm.run_forever()
