#!/bin/env python
#coding:utf8
#execute job by this script

import re
import sys
import time
import uuid
from conf import config

if sys.version_info<(3,0):
    input=raw_input


def get_session_var_name(job_info):
    """
    从playbook中提取session的参数名
    """
    playbook=job_info["playbook"]
    session_vars=[]
    with open(playbook,"r") as f:
        l=f.readline()
        while l:
            #存在bug 旧被获取,如          echo xxx # {{session.YYYY}}
            #但不应排除#只后的字符串 如   echo "#" {{session.YYYY}}
            if not re.match("^#",l):
                #session_vars=session_vars+re.findall("(?<={{session\.).*?(?=}})",l)
                session_vars=session_vars+re.findall("(?<={{"+config.playbook_prefix_session+"\.).*?(?=}})",l)
            l=f.readline()
    return list(set(session_vars))


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


def check_job_result(r,job_id):
    """
    检查统计当前job的执行结果
    """
    complete=[]    
    fail=[]
    uncomplete=[]

    log_job=config.prefix_log_job+job_id
    log_job_dict=r.hgetall(log_job)
    #print(log_job_dict)
    if log_job_dict:
        log_target=eval(log_job_dict["log"])
        for lc in log_target:
            cluster_id=lc[0].split("_")[-1]
            cluster_name=lc[0].split("_"+cluster_id)[0]

            cluster_log_last_info=r.hgetall("sum_"+cluster_id)                              #获取最后一个命令的日志
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


def pause_and_check():
    continue_flag=input("input [yes] to continue: ")
    if continue_flag != "yes":
        print("process abort,bye!")
        exit()


if __name__=="__main__":

    cp=get_var_interactive(["target","playbook"])

    #target="cluster1,cluster2,cluster3"
    #target="cluster1"
    #playbook="/root/test4/a.txt"
    if cp["target"]:
        target=cp["target"]
    else:
        print("target can not be null")
        exit()
    
    if cp["playbook"]:
        playbook=cp["playbook"]
    else:
        print("playbook can not be null")
        exit()    
    
    job_id=uuid.uuid1().hex
    job_name=config.prefix_job+job_id
    session=config.prefix_session+job_id
    
    job_info={"job_id":job_id,"target":target,"playbook":playbook,config.playbook_prefix_session:session,"begin_time":time.time()}    
    job_info["user"]="script"
    job_info["job_type"]="test"
    job_info["comment"]="这是通过脚本运行的"

    #job_info["begin_host"]="182.236.70.137"      #存在跳过时开始执行命令的主机
    #job_info["begin_line"]=18                    #从第几行开始执行 之前的命令全部跳过

    import redis
    from conf.config import *
    #可清除以下
    redis_send_client=redis.StrictRedis(host=redis_send_host, port=redis_send_port, db=redis_send_db, password=redis_send_passwd,decode_responses=True)
    redis_log_client=redis.StrictRedis(host=redis_log_host, port=redis_log_port, db=redis_log_db, password=redis_log_passwd,decode_responses=True)
    #不可清除以下
    redis_config_client=redis.StrictRedis(host=redis_config_host, port=redis_config_port, db=redis_config_db, password=redis_config_passwd,decode_responses=True)
    redis_job_client=redis.StrictRedis(host=redis_job_host, port=redis_job_port, db=redis_job_db, password=redis_job_passwd,decode_responses=True)
    
    redis_job_client.hmset(job_name,job_info)
 
    print("--------------------------init--------------------------"+job_name) 
    
    session_vars=get_session_var_name(job_info)
    session_info=get_var_interactive(session_vars)
    
    print("session info: %s" % str(session_info))
    pause_and_check()
        
    if session_info:
        redis_config_client.hmset(session,session_info)
        redis_config_client.expire(session,config.session_var_expire_sec)
      
    print("--------------------------begin--------------------------"+job_name)
    
    
    redis_send_client.rpush(config.key_job_list,job_name) 


    job_result=check_job_result(redis_log_client,job_id)
    while job_result["uncomplete"] or (not job_result["complete"] and not job_result["uncomplete"] and not job_result["fail"]):
        print(job_result)
        job_result=check_job_result(redis_log_client,job_id)
        time.sleep(1)
    print(job_result)

    #check job log
    if session_info:
        redis_config_client.expire(session,60*60)    

    print("--------------------------done--------------------------"+job_name)
    
    
