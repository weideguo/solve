# -*- coding: utf-8 -*-
import os
import sys
import uuid
import redis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.cluster_exe import ClusterExecution




if __name__=="__main__":
    
    #可清除以下
    redis_send_config={"host":"127.0.0.1", "port":6379, "db":0, "password":"my_redis_passwd"}
    redis_log_config={"host":"127.0.0.1", "port":6379, "db":1, "password":"my_redis_passwd"}
    redis_tmp_config={"host":"127.0.0.1", "port":6379, "db":2, "password":"my_redis_passwd"}
    #不可清除以下
    redis_job_config={"host":"127.0.0.1", "port":6379, "db":14, "password":"my_redis_passwd"}
    redis_config_config={"host":"127.0.0.1", "port":6379, "db":15, "password":"my_redis_passwd"}
    
    cid=uuid.uuid1().hex
    
    ce=ClusterExecution(cid,[redis_send_config,redis_log_config,redis_tmp_config,redis_job_config,redis_config_config])
    p="/root/test4/a.txt"
    ce.run("cluster2",p)

    print("================================================================")
    cid=uuid.uuid1().hex
    ce=ClusterExecution(cid,[redis_send_config,redis_log_config,redis_tmp_config,redis_job_config,redis_config_config])
    ce.run("cluster1",p)

    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
