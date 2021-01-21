# -*- coding: utf-8 -*-
import os
import sys
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
    #from conf import config
    #redis_send=config.redis_send
    
    redis_send_client=rc.init(redis_send)
    
    redis_send_client.info()
    
    redis_send_client=rc.refresh(redis_send,force=True)
    
    redis_send_client.info()
    
    #redis_send_client=rc.refresh(redis_send)
    
    sentinels=redis_send["sentinels"]
    service_name=redis_send["service_name"]
    db=redis_send["db"]
    password=redis_send["password"]
    redis_slave_client=rc.init_sentinel(sentinels, service_name, db, password, is_master=False)
    
    
    #在多线程中共享连接池
    print(redis_send_client.connection_pool.max_connections)
    print(redis_send_client.connection_pool.timeout)
    
    from threading import Thread
    
    def f(c):
        print(c.keys())
    
    
    for i in range(10):
        t=Thread(target=f,args=(redis_send_client,))
        t.start()    
    
    #多线程间共享连接池在redis重启时的处理
    import time
    from threading import Thread
    
    def f(c):
        while True:
            try:
                time.sleep(3)
                #print(c.keys())
                print(c.blpop("__xx__"))
            except:
                print("------------error----------")
    
    
    t=Thread(target=f,args=(redis_send_client,))
    t.start()   

    
    
    
    #多进程间也可共享连接池
    from multiprocessing import Process
    
    def f(c):
        print(c.keys())
    
    
    for i in range(10):
        t=Process(target=f,args=(redis_send_client,))
        t.start()   
 


    #多进程间共享连接池在redis重启时的处理
    import time
    from multiprocessing import Process
    
    def f(c):
        while True:
            try:
                time.sleep(3)
                #print(c.keys())
                print(c.blpop("__xx__"))
            except:
                print("------------error----------")
    
    
    t=Process(target=f,args=(redis_send_client,))
    t.start()   





 
    