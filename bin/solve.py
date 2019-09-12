#!/bin/env python
#coding:utf8
#start server from here
#Simple cOmmand diLiver serVEr
#SOLVE
#by weideguo
import os
import sys
import time

import redis
from core.job_manager import JobManager


if __name__=="__main__":
    from conf import config
    #可清除以下
    redis_send_pool=redis.ConnectionPool(host=config.redis_send_host, port=config.redis_send_port,\
                    db=config.redis_send_db, password=config.redis_send_passwd,decode_responses=True)
    redis_log_pool=redis.ConnectionPool(host=config.redis_log_host, port=config.redis_log_port,\
                    db=config.redis_log_db, password=config.redis_log_passwd,decode_responses=True)
    
    #不可清除以下
    redis_config_pool=redis.ConnectionPool(host=config.redis_config_host, port=config.redis_config_port,\
                        db=config.redis_config_db, password=config.redis_config_passwd,decode_responses=True)
    redis_job_pool=redis.ConnectionPool(host=config.redis_job_host, port=config.redis_job_port,\
                        db=config.redis_job_db, password=config.redis_job_passwd,decode_responses=True)

    jm=JobManager(redis_send_pool,redis_log_pool,redis_job_pool,redis_config_pool)

    
    log_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"../logs")
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    
    stdin_path = "/dev/null"
    stdout_path = os.path.join(log_path, "solve.out")
    stderr_path =  os.path.join(log_path, "solve.err")
    pidfile_path =  os.path.join(log_path, "solve.pid")    
    pidfile_timeout = 5

    class Solve(object):

        stdin_path =  stdin_path
        stdout_path = stdout_path
        stderr_path = stderr_path 
        pidfile_path = pidfile_path
        pidfile_timeout = pidfile_timeout

        def run(self):
            jm.run_forever()


    from lib.logger import logger
    from daemon.runner import DaemonRunner

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
            redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)
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
            
            #由于使用-9 需要自行删除pid文件
            try:
                os.remove(pidfile_path)
            except:
                pass


    run = MyDaemonRunner(Solve())
    run.do_action()
    
    #start restart   
    #logger.info(sys.argv[1])
    if sys.argv[1] != "stop":
        #写日志
        logger.info(sys.argv[1])
        #清除相关key
        if config.clear_start:
            redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)
            k_list=[]
            for k_pattern in [config.key_conn_control,config.prefix_cmd,config.prefix_heart_beat]:
                k_list +=redis_send_client.keys(k_pattern+"*")
            for k in k_list:
                redis_send_client.delete(k)



