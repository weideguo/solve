import redis
from core.plugin.ssh.remote_host import RemoteHost

if __name__=="__main__":
                
    host_info={"ip":"192.168.59.132","user":"root","passwd":"weideguo","ssh_port":22}        
    redis_send_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=0, password="my_redis_passwd",decode_responses=True)        
    redis_log_pool=redis.ConnectionPool(host="127.0.0.1", port=6379, db=1, password="my_redis_passwd",decode_responses=True)        
            
    h=RemoteHost(host_info,redis_send_pool,redis_log_pool) 
    h.forever_run()
   
    #host_info2={"ip":"192.168.59.129","user":"root","passwd":"my_host_pass","ssh_port":22}

    #h2=RemoteHost(host_info2,redis_send_pool,redis_log_pool) 
    #h2.forever_run()

