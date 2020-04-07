#!/bin/env python
#coding:utf8
#start server from here
#Simple cOmmand diLiver serVEr
#SOLVE
#by weideguo
import os
import sys
import time
from multiprocessing import Process

import redis
from daemon.runner import DaemonRunner
    
base_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)
from lib.logger import logger
from core.job_manager import JobManager
from core.proxy_manager import ProxyManager

if __name__=="__main__":
    from conf import config
    #decode_responses=True      将结果自动编码为unicode格式，否则对于python3结果格式为 b'xxx'
    #encoding_errors='ignore'   decode的选项，编码出错时的处理方式，可选 strict ignore replace 默认为strict 
    #可清除以下
    redis_send_pool=redis.ConnectionPool(host=config.redis_send_host, port=config.redis_send_port,\
                    db=config.redis_send_db, password=config.redis_send_passwd,decode_responses=True,encoding_errors='ignore')
    redis_log_pool=redis.ConnectionPool(host=config.redis_log_host, port=config.redis_log_port,\
                    db=config.redis_log_db, password=config.redis_log_passwd,decode_responses=True,encoding_errors='ignore')
    redis_tmp_pool=redis.ConnectionPool(host=config.redis_tmp_host, port=config.redis_tmp_port,\
                    db=config.redis_tmp_db, password=config.redis_tmp_passwd,decode_responses=True,encoding_errors='ignore')
    
    #不可清除以下
    redis_config_pool=redis.ConnectionPool(host=config.redis_config_host, port=config.redis_config_port,\
                        db=config.redis_config_db, password=config.redis_config_passwd,decode_responses=True,\
                        encoding_errors='ignore')
    redis_job_pool=redis.ConnectionPool(host=config.redis_job_host, port=config.redis_job_port,\
                        db=config.redis_job_db, password=config.redis_job_passwd,decode_responses=True,encoding_errors='ignore')
    
    redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)
    
    log_path=os.path.join(base_dir,"./logs")
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    
    stdin_path = "/dev/null"
    stdout_path = os.path.join(log_path, "solve.out")
    stderr_path =  os.path.join(log_path, "solve.err")
    pidfile_path =  os.path.join(log_path, "solve.pid")    
    pidfile_timeout = 5
    
    # 存储pid
    pid_key = "__pid__"
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
    
    manager=Manager(redis_send_pool,redis_log_pool,redis_tmp_pool,redis_job_pool,redis_config_pool)
    
    try:
        opt=sys.argv[1].strip()
        if opt != "stop":
            print('%s mode \033[1;32m %s \033[0m' % (opt,start_mode))
            try:
                print("proxy tag  \033[1;32m %s \033[0m" % manager.proxy_tag[:-1])
            except:
                pass
            if is_start_fileserver:
                print("fileserver listen on  \033[1;32m %s:%d \033[0m" % (config.bind,config.port))
        else:
            print('%s \033[1;32m success \033[0m' % opt) 
    except:
        pass

    
    #启动前对redis的清理与设置
    #start restart 才使用
    def init_set():
        #写日志
        logger.info(opt)
        
        redis_send_client.hset(config_key,"base_dir",config.base_dir)
        if is_start_fileserver:
            listen_host=config.bind
            if config.bind == "0.0.0.0":
                #监听"0.0.0.0"则取一个本地ip
                from lib.utils import get_host_ip
                listen_host=get_host_ip()
                
            redis_send_client.hset(config_key,"fileserver_bind",listen_host)
            redis_send_client.hset(config_key,"fileserver_port",config.port)
        #清除存储的pid
        redis_send_client.delete(pid_key)
        
        #清除相关key
        if config.clear_start:
            #redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)
            k_list=[]
            for k_pattern in [config.key_conn_control,config.prefix_cmd,config.prefix_heart_beat]:
                k_list +=redis_send_client.keys(k_pattern+"*")
            for k in k_list:
                redis_send_client.delete(k)

    def start_fileserver():
        """
        web服务用于文件管理
        """
        if is_start_fileserver:
            from core.fileserver import fileserver
            bind=config.bind
            port=config.port
            origin=config.origin
            
            p=Process(target=fileserver.start, args=(bind,port,log_path,origin))
            p.start()
            redis_send_client.rpush(pid_key,p.pid)    
    
    class Solve(object):

        stdin_path =  stdin_path
        stdout_path = stdout_path
        stderr_path = stderr_path 
        pidfile_path = pidfile_path
        pidfile_timeout = pidfile_timeout
        
        def run(self):
            init_set()
            start_fileserver()
            manager.run_forever()
    
    
    class MyDaemonRunner(DaemonRunner):
        """
        重载以下方法
        daemon可以防止多次启动
        """

        def _open_streams_from_app_stream_paths(self, app):
            self.daemon_context.stdin = open(app.stdin_path, 'r')
            self.daemon_context.stdout = open(app.stdout_path, 'a+')
            self.daemon_context.stderr = open(app.stderr_path, 'a+')
       
        def _terminate_daemon_process(self):
            #结束进程时
            #清理心跳包
            
            hbs=redis_send_client.keys(config.prefix_heart_beat+"*")
            for h in hbs:
                redis_send_client.delete(h)
        
            #写日志
            with open(stdout_path,'a+') as f:
                f.write("%s,000 - %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()), 'stop'))

            #python2.7时结束进程时需要使用kill -9
            import signal
            signal.SIGTERM=9
            #super()._terminate_daemon_process()  
            super(MyDaemonRunner,self)._terminate_daemon_process()  
            
            #杀死子进程
            pid=redis_send_client.lpop(pid_key)
            while pid:
                os.kill(int(pid), signal.SIGTERM)
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

    