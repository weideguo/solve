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

from daemon.runner import DaemonRunner
    
base_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)
from lib.redis_conn import RedisConn
#from lib.logger import logger,logger_err
from lib.wrapper import logger,logger_err
from core.job_manager import JobManager
from core.proxy_manager import ProxyManager



solve_logo="""
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
            start_mode=sys.argv[2].strip()
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
    
    try:
        opt=sys.argv[1].strip()
        if opt != "stop":
            if opt == "start":
                print("\033[1;32m %s \033[0m" % solve_logo)
                print("%s mode \033[1;32m %s \033[0m" % (opt,start_mode))
            try:
                #for proxy mode
                print("proxy tag  \033[1;32m %s \033[0m" % manager.proxy_tag)
                config_key=config_key+manager.proxy_mark
            except:
                pass
            if is_start_fileserver:
                print("fileserver listen on  \033[1;32m %s:%d \033[0m" % (config.bind,config.port))
        else:
            print("%s \033[1;32m success \033[0m" % opt) 
    except:
        pass

    def simple_log(msg):
        return "%s,000 - %s" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),msg)
    
    #启动前对redis的清理与设置
    #start restart 才使用
    def init_set():
        #写日志
        logger.info(opt)
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
            clear_keys=[config.key_conn_control,config.prefix_cmd,config.prefix_heart_beat]
            print(simple_log("clear key %s" % str(clear_keys)))
            k_list=[]
            for k_pattern in clear_keys:
                k_list +=redis_send_client.keys(k_pattern+"*")
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
    
    
    class MyDaemonRunner(DaemonRunner):
        """
        重载以下方法
        daemon可以防止多次启动
        """

        def _open_streams_from_app_stream_paths(self, app):
            self.daemon_context.stdin = open(app.stdin_path, "r")
            self.daemon_context.stdout = open(app.stdout_path, "a+")
            self.daemon_context.stderr = open(app.stderr_path, "a+")
       
        def _terminate_daemon_process(self):
            #结束进程时
            #清理心跳包
            
            hbs=redis_send_client.keys(config.prefix_heart_beat+"*")
            for h in hbs:
                redis_send_client.delete(h)
        
            #写日志
            with open(stdout_path,"a+") as f:
                #f.write("%s,000 - %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), "stop"))
                f.write(simple_log("stop\n"))

            #python2.7时结束进程时需要使用kill -9
            import signal
            signal.SIGTERM=9
            
            #杀主进程
            #super()._terminate_daemon_process()  
            super(MyDaemonRunner,self)._terminate_daemon_process()  
            
            #杀死子进程
            pid_key = "__pid__"
            pid_key=pid_key+str(self.pidfile.read_pid())
            pid=redis_send_client.lpop(pid_key)
            while pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except:
                    pass
                pid=redis_send_client.lpop(pid_key)
            
            #由于使用-9 需要自行删除pid文件
            try:
                os.remove(pidfile_path)
            except:
                pass

    
    run = MyDaemonRunner(Solve())
    run.do_action()
    #在此之后的所有操作会被跳过
    #不要放任何操作在此之后

    