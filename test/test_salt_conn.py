#coding:utf8
import os
import sys
import redis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.plugin.salt.salt_conn import SaltConn

if __name__ == "__main__":

    host_info={"ip":"192.168.59.132","user":"root","passwd":"my_host_pass","ssh_port":22}
    
    redis_send_config={"host":"127.0.0.1", "port":6379, "db":0, "password":"my_redis_passwd"}
    redis_log_config={"host":"127.0.0.1", "port":6379, "db":1, "password":"my_redis_passwd"}
    
    h=SaltConn(host_info,[redis_send_config,redis_log_config])  
    
