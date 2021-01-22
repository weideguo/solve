# -*- coding: utf-8 -*-
import os
import re
import time
import uuid
import importlib
from traceback import format_exc

from .localhost import LocalHost
from lib.wrapper import logger,logger_err
from conf import config


module_name, class_name = config.remote_model.rsplit('.', 1)
mod = importlib.import_module(module_name)
RemoteHost = getattr(mod, class_name)

class BaseManager(object):
    """
    基础任务执行管理类
    """    

    def __init__(self, redis_connect, redis_config_list):
        
        self.redis_send_config=redis_config_list[0]
        self.redis_log_config=redis_config_list[1]
        self.redis_tmp_config=redis_config_list[2]
        self.redis_job_config=redis_config_list[3]       
        self.redis_config_config=redis_config_list[4]
        
        self.redis_config_list=redis_config_list
        self.redis_connect=redis_connect
        
        self.redis_refresh()
        
        self.playbook_dir="playbook"    #存放playbook的目录 使用相对目录时使用
        
        self.listen_tag = config.local_ip_list
   
   
    def redis_refresh(self):
        self.redis_send_client=self.redis_connect.refresh(self.redis_send_config)
        self.redis_log_client=self.redis_connect.refresh(self.redis_log_config) 
        self.redis_tmp_client=self.redis_connect.refresh(self.redis_tmp_config)
        self.redis_job_client=self.redis_connect.refresh(self.redis_job_config)        
        self.redis_config_client=self.redis_connect.refresh(self.redis_config_config)           
    
    
    def is_listen_tag_clean(self):
        """
        启动本地时检查是否已经存在旧的命令
        """
        for init_host in self.listen_tag:
            if self.redis_send_client.llen(config.prefix_cmd+init_host):
                raise Exception("%s should be null" % (config.prefix_cmd+init_host))
    
    
    def localhost(self):
        """
        对本地的操作不需要再使用连接
        """
        #进程自己创建连接池 单个进程内的线程共享
        redis_connect=None
        logger.debug("localhost start, listen on: %s" % str(self.listen_tag))
        lh=LocalHost([self.redis_send_config,self.redis_log_config],self.listen_tag,redis_connect=redis_connect) 
        lh.forever_run() 
        #阻塞运行，以下操作不应该被运行
        logger_err.error("localhost should not end, something error!")
        

    def is_host_alive(self,ip,lock=True):
        """
        判断SSH是否已经连接
        一个主机只能运行允许一个并发进行判断
        """
        if config.cluster_connect_control:
            #当使用cluster控制连接关闭时 不加锁 
            #只有本地连接有ip的心跳  非本地有uuid的心跳
            lock=False
        
        if lock:
            check_flag=self.redis_send_client.set(config.prefix_check_flag+ip,1,nx=True)
        else:
            check_flag=not self.redis_send_client.get(config.prefix_check_flag+ip)
            
        #拿不到判断的flag则默认服务是连接的 存在心跳则服务是连接的 
        if not check_flag or self.redis_send_client.exists(config.prefix_heart_beat+ip):
            is_alive=True
        else:
            is_alive=False
            
        return is_alive
    
    
    def conn_host(self,init_host,redis_connect,init_host_uuid):
        """
        远端主机连接
        """
        try:
            #如果连接存在 则不必再创建 否则则新建连接 
            if not self.is_host_alive(init_host):
                host_info=self.redis_config_client.hgetall(config.prefix_realhost+init_host)
                if config.cluster_connect_control:
                    host_info["uuid"]=init_host_uuid
                host_info["tag"]=host_info["ip"]
                host_info["ip"]=host_info["ip"].split("_")[0]
                           
                if not ("ip" in host_info): 
                    self.redis_log_client.hset(init_host_uuid,"exit_code","host info err")
                    logger_err.error("< %s > init failed, host info error, ip not exist" % init_host)
    
                elif not self.redis_send_client.llen(config.prefix_cmd+init_host) or not config.host_start_without_cmd:                
                        
                    logger.debug("init host info %s" % str(host_info))
            
                    try: 
                        self.redis_send_client.set(config.prefix_initing+init_host,time.time())
                        h=RemoteHost(host_info,[self.redis_send_config,self.redis_log_config])
                        h.forever_run()
                        logger.info("< %s > init success" % init_host)                    
                    except:
                        self.redis_log_client.hset(init_host_uuid,"exit_code","init failed")
                        self.redis_log_client.hset(init_host_uuid,"stderr",format_exc())
                        self.redis_send_client.set(config.prefix_initing+init_host,-1)
                        logger_err.error(format_exc())
                        logger_err.error("< %s > init failed" % init_host)
                        
                    self.redis_send_client.expire(config.prefix_initing+init_host,config.initing_host_flag_expire_sec)
                else:
                    self.redis_log_client.hset(init_host_uuid,"exit_code","cmd exist")
                    logger_err.error("< %s > not shutdown clean before,will not init. please check cmd_%s" % (init_host,init_host))
                
                self.redis_send_client.delete(config.prefix_check_flag+init_host)           #连接不存在时操作完毕才释放锁 
            else:
                self.redis_log_client.hset(init_host_uuid,"stdout","connect exist,init skip")        
                logger.debug("< %s > init skipped" % init_host)    
        except:
            self.redis_send_client.delete(config.prefix_check_flag+init_host)               #发生异常释放锁 
            self.redis_log_client.hset(init_host_uuid,"exit_code","init failed")
            self.redis_log_client.hset(init_host_uuid,"stderr",format_exc())
            logger_err.error(format_exc())
    
    
    def process_run(self,p_list,redis_client=None,pid_key="__pid__"):
        """
        运行进程
        """
        for p in p_list:
            p.start()
        
        self.pid_key=pid_key+str(os.getpid())
        
        #使用redis保存子进程的pid
        if redis_client:
            for p in p_list:
                redis_client.rpush(self.pid_key,p.pid)


    def run_forever(self):
        """提供给实际运行，必须重载"""
        raise Exception('.run_forever() must be overridden')  
    