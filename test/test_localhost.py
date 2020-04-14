#coding:utf8
import os
import sys
import redis
import time
from threading import Thread

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.localhost import LocalHost

if __name__=="__main__":
    
    redis_send_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=0, password="my_redis_passwd",decode_responses=True)        
    redis_log_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=1, password="my_redis_passwd",decode_responses=True)        
    #listen_tag=["127.0.0.1","localhost"]        
    
    listen_tag=["proxy:192.168.153.128:127.0.0.1"]
    
    redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)
    redis_log_client=redis.StrictRedis(connection_pool=redis_log_pool)
    lh=LocalHost(redis_send_client,redis_log_client,listen_tag) 
    lh.forever_run()
    """
    
    def f3():
        redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)
        for init_host in listen_tag:
            if redis_send_client.llen("cmd_"+init_host):
                raise Exception("%s should be null" % ("cmd_"+init_host))
    def f():
        print("start")
        lh=LocalHost(redis_send_client,redis_log_client,listen_tag) 
        lh.forever_run()
    
    def f2():
        
        while True:
            print("xxx")
            time.sleep(3)
            
    f3()
        
    t=Thread(target=f)
    t2=Thread(target=f2)
    try:
        t.start()
    except:
        raise Exception("xxxxxxxxxxxx")
    t2.start()
    
    while True:
        print("yyy")
        time.sleep(5)
            
    """        
            
    #(self,redis_send_client,redis_log_client,listen_tag,t_number=5)
    #host_info2={"ip":"192.168.59.129","user":"root","passwd":"my_host_pass","ssh_port":22}

    #h2=RemoteHost(host_info2,redis_send_client,redis_log_client) 
    #h2.forever_run()

