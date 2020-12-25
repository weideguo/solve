# -*- coding: utf-8 -*-
import os
import sys
import redis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.plugin.ssh.remote_host import RemoteHost

if __name__=="__main__":
                
    host_info={"ip":"192.168.253.128","user":"root","passwd":"weideguo","ssh_port":22,"uuid":"a032fda245b911eba18f005056337d90"}        
    
    #redis_send_config={"host":"127.0.0.1", "port":6379, "db":0, "password":"my_redis_passwd"}
    #redis_log_config={"host":"127.0.0.1", "port":6379, "db":1, "password":"my_redis_passwd"}
    from conf import config
    redis_send_config=config.redis_send
    redis_log_config=config.redis_log
    
    h=RemoteHost(host_info,[redis_send_config,redis_log_config]) 
    h.forever_run()
   
    #host_info2={"ip":"192.168.59.129","user":"root","passwd":"my_host_pass","ssh_port":22}

    #h2=RemoteHost(host_info2,[redis_send_config,redis_log_config] 
    #h2.forever_run()

