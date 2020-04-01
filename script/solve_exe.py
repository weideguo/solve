#!/bin/env python
#coding:utf8
#execute job by this script

import os
import re
import sys
import time
import uuid
import redis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conf import config


class SolveExe():
    """
    使用solve执行job
    """
    
    job_info={}
    
    job_id=uuid.uuid1().hex
    job_name=config.prefix_job+job_id
    session=config.prefix_session+config.spliter+job_id
    
    job_info["job_id"]=job_id  
    job_info["target"]=""                       #必须在初始时设置 cluter1,cluter2,cluter3
    job_info["playbook"]=""                     #必须在初始时设置 文件路径
    job_info[config.prefix_session]=session
    job_info["begin_time"]=time.time()   
    job_info["user"]="script"
    job_info["job_type"]="test"
    job_info["comment"]="这是通过脚本运行的"
    
    job_info["begin_line"]=0                    #从第几行开始执行 之前的命令全部跳过 非零时必须设置begin_host
    job_info["begin_host"]=""                   #存在跳过时开始执行命令的主机
    
    
    def __init__(self,redis_send_client,redis_log_client,redis_tmp_client,redis_job_client,job_info={}):
        self.redis_send_client    = redis_send_client
        self.redis_log_client     = redis_log_client
        self.redis_tmp_client  = redis_tmp_client
        self.redis_job_client     = redis_job_client
    
        for k in job_info:
            self.job_info[k] = job_info[k]
    

    def get_session_var_name(self):
        """
        从playbook中提取session的参数名
        """
        playbook=self.job_info["playbook"]
        session_vars=[]
        
        playbook=os.path.join(config.base_dir,"playbook",playbook)
        with open(playbook,"r") as f:
            l=f.readline()
            while l:
                #存在bug 旧被获取,如          echo xxx # {{session.YYYY}}
                #但不应排除#只后的字符串 如   echo "#" {{session.YYYY}}
                if not re.match("^#",l):
                    #session_vars=session_vars+re.findall("(?<={{session\.).*?(?=}})",l)
                    session_vars=session_vars+re.findall("(?<={{"+config.prefix_session+"\.).*?(?=}})",l)
                l=f.readline()
        return list(set(session_vars))
    
    
    def set_session(self,session_info={}):
        """
        设置session
        """
        if session_info:
            self.redis_tmp_client.hmset(self.session,session_info)
            self.redis_tmp_client.expire(self.session,config.tmp_config_expire_sec)
    
    
    def exe(self):
        """
        执行
        """
        self.redis_job_client.hmset(self.job_name,self.job_info)
        self.redis_send_client.rpush(config.key_job_list,self.job_name)
        return self.job_name
    
    
    def check_job_result(self):
        """
        检查统计当前job的执行结果
        """
        complete=[]    
        fail=[]
        uncomplete=[]
    
        log_job=config.prefix_log_job+self.job_id
        log_job_dict=self.redis_log_client.hgetall(log_job)
        #print(log_job_dict)
        if log_job_dict:
            log_target=eval(log_job_dict["log"])
            for lc in log_target:
                #cluster_id=lc[0].split("_")[-1]
                #cluster_name=lc[0].split("_"+cluster_id)[0]
                cluster_id=lc[0].split(config.spliter)[-1]
                cluster_name=lc[0].split(config.spliter+cluster_id)[0]
    
                cluster_log_last_info=self.redis_log_client.hgetall("sum_"+cluster_id)                              #获取最后一个命令的日志
                #print(cluster_log_last_info)
                if ("stop_str" in cluster_log_last_info) and ("end_timestamp" in cluster_log_last_info):
                    if cluster_log_last_info["stop_str"]=="done":
                        complete.append(cluster_name)
                    else:
                        fail.append(cluster_name)
                else:
                    uncomplete.append(cluster_name)
    
        result_sum={"complete":complete,"fail":fail,"uncomplete":uncomplete}
        return result_sum

    def key_expire(self):
        self.redis_tmp_client.expire(self.session,config.tmp_config_expire_sec) 



if __name__=="__main__":
    
    #可清除以下
    redis_send_client=redis.StrictRedis(host=config.redis_send_host, port=config.redis_send_port, \
                                        db=config.redis_send_db, password=config.redis_send_passwd,decode_responses=True)
    redis_log_client=redis.StrictRedis(host=config.redis_log_host, port=config.redis_log_port, \
                                       db=config.redis_log_db, password=config.redis_log_passwd,decode_responses=True)
    #不可清除以下
    redis_tmp_client=redis.StrictRedis(host=config.redis_tmp_host, port=config.redis_tmp_port, \
                                          db=config.redis_tmp_db, password=config.redis_tmp_passwd,decode_responses=True)
    redis_job_client=redis.StrictRedis(host=config.redis_job_host, port=config.redis_job_port, \
                                       db=config.redis_job_db, password=config.redis_job_passwd,decode_responses=True)
  


    if sys.version_info<(3,0):
        input=raw_input

    def get_var_interactive(var_list):
        """
        通过交互获取参数值
        """
        args={}
        for k in var_list:
            p="%s: " % k
            v=input(p)
            args[k]=v.strip()   
        
        return args

    def pause_and_check():
        if input("input [yes] to continue: ") != "yes":
            print("process abort,bye!")
            exit()
    
    new_info=get_var_interactive(["target","playbook"])

    for k in new_info:
        if not new_info["target"]:
            print("%s can not be null" % k)
            exit()
     
    se=SolveExe(redis_send_client,redis_log_client,redis_tmp_client,redis_job_client,new_info)
    
    print("--------------------------init--------------------------"+se.job_name) 
    
    session_vars=se.get_session_var_name()
    
    session_info=get_var_interactive(session_vars)
    print("session info: %s" % str(session_info))
    pause_and_check()
        
    se.set_session(session_info)
      
    print("--------------------------begin--------------------------"+se.job_name)
        
    se.exe()  

    job_result=se.check_job_result()
    while job_result["uncomplete"] or (not job_result["complete"] and not job_result["uncomplete"] and not job_result["fail"]):
        print(job_result)
        time.sleep(1)
        job_result=se.check_job_result()
    
    print(job_result)
    
    se.key_expire()  

    print("--------------------------done--------------------------"+se.job_name)
    
    
