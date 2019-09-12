#coding:utf8
import redis
from core.job_manager import JobManager



if __name__=="__main__":
    #可清除以下
    redis_send_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=0, password="my_passwd",decode_responses=True)
    redis_log_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=1, password="my_passwd",decode_responses=True)
    #不可清除以下
    redis_config_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=15, password="my_passwd",decode_responses=True)
    redis_job_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=14, password="my_passwd",decode_responses=True)

    jm=JobManager(redis_send_pool,redis_log_pool,redis_job_pool,redis_config_pool)
    jm.run_forever()
