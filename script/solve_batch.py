#coding:utf8
#用于单次命令分发
import uuid
import time
import redis

from multiprocessing import Process

from conf import config


class SolveBatch():
    """
    对大量主机使用solve批量执行一个shell命令
    """    
         
    def __init__(self,redis_send_client,redis_log_client):
        self.redis_send_client=redis_send_client
        self.redis_log_client=redis_log_client
    
    
    def conn(self,target_list):
        """
        发送连接信息 
        """
        for target in target_list:
            self.redis_send_client.rpush(config.key_conn_control,target[0]+config.cmd_spliter+target[1])    
    
        
    def connect_check(self,target_list):
        """
        以生成器形式获取已经连接的主机
        如果判断超时则 跳过
        [(ip,id),(ip2,id2)]
        """    
                
        def get_heart_beat(current_host):
            heart_beat=self.redis_send_client.get(config.prefix_heart_beat+current_host)
            if not heart_beat:
                heart_beat=0
            return heart_beat
    
        retry_flag=0
        while retry_flag<config.host_check_wait and target_list:
            print(retry_flag,target_list)
            for target in target_list:
                if time.time()-float(get_heart_beat(target[0]))<=config.host_check_success_time:     
                    yield target
                    target_list.remove(target) 
                elif ("exit_code" in self.redis_log_client.hgetall(target[1])) and \
                     str(self.redis_log_client.hget(target[1],"exit_code")) !="0":
                    target_list.remove(target)
                else:
                    pass
            
            time.sleep(1) 
            retry_flag = retry_flag+1
        
     
    def __exe(self,target_list,cmd):
        """
        对已经存在连接主机执行命令
        """
        for target in self.connect_check(target_list):
            self.redis_send_client.rpush(config.prefix_cmd+target[0],cmd+config.cmd_spliter+target[1])
    
    
    def exe(self,target_list,cmd):
        """
        使用一个并发执行运行
        """
        p=Process(target=self.__exe,args=(target_list,cmd))
        p.start()
        return p
    
    
    def get_result(self,target_list,process,is_sync=False):
        """
        获取执行结果 
        is_sync 是否在连接判断完毕后再获取
        """
        if is_sync:
            process.join()
        
        for target in target_list:
            yield target,self.redis_log_client.hgetall(target[1])
    
    
if __name__=="__main__":
    redis_send_pool=redis.ConnectionPool(host=config.redis_send_host, port=config.redis_send_port,\
                db=config.redis_send_db, password=config.redis_send_passwd,decode_responses=True)

    redis_log_pool=redis.ConnectionPool(host=config.redis_log_host, port=config.redis_log_port,\
                   db=config.redis_log_db, password=config.redis_log_passwd,decode_responses=True)

    redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)
    redis_log_client=redis.StrictRedis(connection_pool=redis_log_pool)
 

    sb=SolveBatch(redis_send_client,redis_log_client)

    import sys
    if sys.version_info<(3,0):
        input=raw_input

    ip_str=input("ip str: ")
    if not ip_str:
        print("ip str can not be null")
        exit()

    cmd=input("cmd: ")
    if not cmd:
        print("cmd can not be null")
        exit()

    #ip_str="192.168.59.111,192.168.59.131,192.168.59.132,192.168.59.199"
    #cmd="who"

    tl=[]
    for ip in ip_str.split(","):
        tl.append((ip,uuid.uuid1().hex))
    
    
    sb.conn(tl)
    p=sb.exe(tl,cmd)
    
    #可能单次获取结果不全 可以多次获取
    print("----------------------------result------------------------------------")
    for r in sb.get_result(tl,p,True):
        print(r)

    
