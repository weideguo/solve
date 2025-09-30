#!/bin/env python
# -*- coding: utf-8 -*-
#start server from here
#Simple cOmmand diLiver serVEr
#SOLVE
#by weideguo
import os
import sys
import time
from multiprocessing import Process
    
base_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)
from lib.redis_conn import RedisConn
from lib.wrapper import logger,logger_err
from core.job_manager import JobManager
from core.proxy_manager import ProxyManager



solve_logo=r"""
 _____ _____ _ __   __ _____     
|   __|     | |\ \ / /|  ___|    
|__   |  |  | |_\ V / |  ___|   
|_____|_____|___|\_/  |_____|   
    
"""


if __name__=="__main__":
    from conf import config
    
    rc=RedisConn(max_connections=config.shared_redis_pool_size)                 #max_connections只是对于单个连接池 使用时每个db对应一个连接池
    #redis客户端线程/进程安全，可以复用
    redis_send_client=rc.init(config.redis_send)
    #redis_log_client=rc.init(config.redis_log)
    #redis_tmp_client=rc.init(config.redis_tmp)
    #redis_job_client=rc.init(config.redis_job)
    #redis_config_client=rc.init(config.redis_config)            
    
    
    log_path=os.path.join(base_dir,"./logs")
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    
    stdin_path = "/dev/null"
    stdout_path = os.path.join(log_path, "solve.out")
    stderr_path =  os.path.join(log_path, "solve.err")
    pidfile_path =  os.path.join(log_path, "solve.pid")    
    pidfile_timeout = 5
    
    # 存储运行时的一些配置，如：
    # playbook的根目录
    # fileserver的ip以及端口
    config_key = "__solve__"    

    
    #是否启用文件管理模块
    try:
        is_start_fileserver=config.fileserver
    except:
        is_start_fileserver=False
    
    mode=["master","proxy"]
    try:
        #如果命令行存在输入 则以命令行优先
        try:
            start_mode=sys.argv[1].strip()
        except:
            start_mode=None
        
        #如果命令行获取失败 则以配置文件为准
        if not start_mode:    
            if config.PROXY:
                start_mode=mode[1]
    except:
        pass
        
    #默认为master模式    
    if not start_mode in mode:        
        start_mode=mode[0]
        
    if start_mode==mode[0]:
        Manager=JobManager
    elif start_mode==mode[1]:
        Manager=ProxyManager
    
    manager=Manager(rc,[config.redis_send,config.redis_log,config.redis_tmp,config.redis_job,config.redis_config])
    
    print("\033[1;32m %s \033[0m" % solve_logo)
    print("%s mode \033[1;32m %s \033[0m" % ("start",start_mode))
    try:
        #for proxy mode
        print("proxy tag  \033[1;32m %s \033[0m" % manager.proxy_tag)
        config_key = config_key+manager.proxy_mark
    except:
        pass
    if is_start_fileserver:
        print("fileserver listen on  \033[1;32m %s:%d \033[0m" % (config.bind,config.port))


    #启动前对redis的清理与设置
    #start
    def init_set():
        #写日志
        logger.info("start")
        #启动时清除旧数据
        redis_send_client.delete(config_key)
        #重新设置新数据
        redis_send_client.hset(config_key,"base_dir",config.base_dir)
        if is_start_fileserver:
            listen_host=config.bind
            if config.bind == "0.0.0.0":
                #监听"0.0.0.0"则取一个本地ip
                from lib.utils import get_host_ip
                listen_host=get_host_ip()
                
            redis_send_client.hset(config_key,"fileserver_bind",listen_host)
            redis_send_client.hset(config_key,"fileserver_port",config.port)
        
        #清除相关key
        if config.clear_start and Manager != ProxyManager:
            clear_keys=[config.key_conn_control,config.prefix_cmd,config.prefix_heart_beat,config.prefix_log_now]
            logger.info("clear key %s" % str(clear_keys))
            k_list=[]
            for k_pattern in clear_keys:
                k_list += list(redis_send_client.scan_iter(k_pattern+"*"))
            for k in k_list:
                redis_send_client.delete(k)

    def start_fileserver():
        """
        web服务用于文件管理
        """
        if is_start_fileserver:
            from fileserver import fileserver
            bind=config.bind
            port=config.port
            origin=config.origin
            
            p=Process(target=fileserver.start, args=(bind,port,log_path,origin))
            p.start()
        else:
            p=None
        return p
    
    class Solve(object):

        stdin_path =  stdin_path
        stdout_path = stdout_path
        stderr_path = stderr_path 
        pidfile_path = pidfile_path
        pidfile_timeout = pidfile_timeout
        
        def run(self):
            init_set()
            p_list=manager.run_forever()
            p=start_fileserver()
            if p:
                redis_send_client.rpush(manager.pid_key,p.pid)  
                p_list.append(p)
            
            #等待所有子进程
            for p in p_list:
                p.join()
    
    
    Solve().run()
    