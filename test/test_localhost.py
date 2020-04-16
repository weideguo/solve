#coding:utf8
import os
import sys
import redis
import time
from threading import Thread

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.localhost import LocalHost

if __name__=="__main__":
    
    redis_send_config={"host":"127.0.0.1", "port":6379, "db":0, "password":"my_redis_passwd"}
    redis_log_config={"host":"127.0.0.1", "port":6379, "db":1, "password":"my_redis_passwd"}
    
    listen_tag=["127.0.0.1","localhost"]        
    
    #listen_tag=["proxy:192.168.153.128:127.0.0.1"]
    
    lh=LocalHost([redis_send_config,redis_log_config],listen_tag) 
    lh.forever_run()
    

