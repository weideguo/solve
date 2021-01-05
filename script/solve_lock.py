#!/bin/env python
# -*- coding: utf-8 -*-
#inspect and release lock in solve
#
import os
import sys
import copy

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conf import config
from lib.redis_conn import RedisConn
from lib.compat import input


class SolveLock(object):

    def __init__(self,host):
        self.cmd_key= config.prefix_cmd + host            
        self.heart_beat_key= config.prefix_heart_beat + host 
        
        self.put_key=config.prefix_put + host
        
        self.redis_connect=RedisConn()
        self.redis_init()
        
        self.cmd_lock="CMD"
        self.file_lock_detail=[]
        self.cmd_lock_detail=[]
        self.lock_list=[]
        

    def redis_init(self):
        self.redis_send_client  =self.redis_connect.init(config.redis_send)
        self.redis_log_client   =self.redis_connect.init(config.redis_log)
        self.redis_tmp_client   =self.redis_connect.init(config.redis_tmp)
        self.redis_job_client   =self.redis_connect.init(config.redis_job)
        self.redis_config_client=self.redis_connect.init(config.redis_config)
    
    
    def get_cmd_lock(self):
        """
        主机的命令队列存在会导致主机不能启动（这样做是防止启动时执行过期的命令）
        通过检查没有heartbeat但存在命令队列确定
        """
        if not self.redis_send_client.exists(self.heart_beat_key):
            return self.redis_send_client.lrange(self.cmd_key,0,self.redis_send_client.llen(self.cmd_key))
        else:
            return []
        
        
    def get_file_lock(self):
        """
        文件存在锁时会导致并发等待很久时间（这样做是防止并发执行时重复上传相同文件，文件相同与否由md5确定）
        通过检查文件日志中存在md5但文件路径为空确定
        """
        file_lock_list=[]
        put_file_info=self.redis_log_client.hgetall(self.put_key)
        for m in put_file_info:
            #print(put_file_info[m], not put_file_info[m])
            if not put_file_info[m]:
                file_lock_list.append(m)
        
        return file_lock_list
    
    
    def get_lock(self): 
        self.file_lock_detail=self.get_file_lock()
        self.cmd_lock_detail=self.get_cmd_lock()
    
        self.lock_list=copy.deepcopy(self.file_lock_detail)
        if self.cmd_lock_detail:
            self.lock_list.append(self.cmd_lock)

    
    def release_lock(self,lock_str,skip_err=False,spliter=","):
        """
        释放锁
        """
        for _lock in lock_str.split(spliter):
            if _lock in self.lock_list:
                if _lock==self.cmd_lock:
                    self.redis_send_client.delete(self.cmd_key)
                else:
                    self.redis_log_client.hdel(self.put_key,_lock)
                
            elif not skip_err:
                print("%s not found in lock list %s" % (_lock,",".join(self.lock_list)))
                break
                
if __name__ == "__main__":
    
    if len(sys.argv)==1 or len(sys.argv)>3 or \
        (len(sys.argv)==2 and sys.argv[1] in [ "--help","-h", "-a", "-r","-f"]) or \
        (len(sys.argv)==3 and sys.argv[1] not in [ "-a", "-r","-f"]) :
        print("useage:")
        print("%s [ --help | -h | -a | -r | -f ] <host>" % sys.argv[0])
        exit(1)
         
    #if sys.version_info<(3,0):
    #    input=raw_input
         
    #host=input("host: ")
    host=sys.argv[-1]
    #print(host)
    #exit(1)
    
    sl=SolveLock(host)
    sl.get_lock()
                
    if len(sys.argv)==2 or sys.argv[1]=="-a":
        if len(sys.argv)==3:
            print("--cmd lock detail")
            print(sl.cmd_lock_detail)
            print("--file lock detail")
            print(sl.file_lock_detail)
    
        print("------------------lock info---------------")
        if not sl.lock_list:
            print("no lock exist")
        else:
            print(",".join(sl.lock_list))     
    
    elif sys.argv[1] in ["-r","-f"]:      
        if not sl.lock_list:
            print("no lock exist")
        else:
            force=sys.argv[1]=="-f"
            if force:
                print("release in force")
            lock_str=input("chose lock to release: %s\n" % ",".join(sl.lock_list))
            print(lock_str)
            sl.release_lock(lock_str,force)
        
    
    print("-----------------------done-----------------------------------------------")

"""    
rc=RedisConn()    
rc.init(config.redis_send)
rc.init(config.redis_log)    
rc.init(config.redis_tmp)    
rc.init(config.redis_job)    
rc.init(config.redis_config) 
"""


   