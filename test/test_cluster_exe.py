import uuid
import redis

from core.cluster_exe import ClusterExecution




if __name__=="__main__":
    redis_config_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=15, password="my_passwd",decode_responses=True)
    redis_send_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=0, password="my_passwd",decode_responses=True)
    redis_log_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=1, password="my_passwd",decode_responses=True)

    ce=ClusterExecution(redis_config_pool,redis_send_pool,redis_log_pool)
    p="/root/test4/a.txt"
    cid=uuid.uuid1().hex
    ce.run("cluster2",p,cid)

    print "================================================================"
    ce=ClusterExecution(redis_config_pool,redis_send_pool,redis_log_pool)
    cid=uuid.uuid1().hex
    ce.run("cluster1",p,cid)

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
