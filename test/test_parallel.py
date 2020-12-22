#coding:utf8

from core.abstract.parallel import AbstractThread

import time
from conf import config

from lib.redis_conn import RedisConn
import random
_redis_connect=RedisConn()       
redis_send_client=_redis_connect.refresh(config.redis_send)  

class MyOPT(AbstractThread):
    
    def __init__(self):
        self.run_flag=True
        self.init_parallel(3,False,True)
        self.thread_list=[]
        self.parallel_list=["bbbb","aaaa"]
        
    
    def real_func(self,a,b):
        #a,b=f()
        int(a[1])
        x=random.random()*3
        print(str(x)+" begin")
        time.sleep(x)
        print(x, a, b)
    
    
  
    def get_func_args(self,k):
        t_allcmd=redis_send_client.blpop(k)  
        #int(t_allcmd[1])
        if not self.run_flag:
            raise Exception("stop ppppppppppppppppp")
        
        return t_allcmd,"xxx"

           

m=MyOPT()
m.serve_forever()



