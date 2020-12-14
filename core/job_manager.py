# -*- coding: utf-8 -*-
import os
import re
import time
import uuid
import importlib
from threading import Thread
from multiprocessing import Process
from traceback import format_exc

from .localhost import LocalHost
from .cluster_exe import ClusterExecution
from lib.utils import my_md5,file_row_count
#from lib.logger import logger,logger_err
from lib.wrapper import connection_error_rerun,logger,logger_err
from lib.redis_conn import RedisConn
from conf import config



class_name = config.remote_model.split(".")[-1]
module_name = ".".join(config.remote_model.split(".")[:-1])
mod = importlib.import_module(module_name)
RemoteHost = getattr(mod, class_name)

class JobManager(object):
    """
    任务执行管理类
    持续监听redis队列获取任务并执行
    SSH连接与关闭的控制
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
   
   
    def redis_refresh(self):
        self.redis_send_client=self.redis_connect.refresh(self.redis_send_config)
        self.redis_log_client=self.redis_connect.refresh(self.redis_log_config) 
        self.redis_tmp_client=self.redis_connect.refresh(self.redis_tmp_config)
        self.redis_job_client=self.redis_connect.refresh(self.redis_job_config)        
        self.redis_config_client=self.redis_connect.refresh(self.redis_config_config)           
    
    
    def is_listen_tag_clean(self,listen_tag=config.local_ip_list):
        #启动本地时检查是否已经存在旧的命令
        for init_host in listen_tag:
            if self.redis_send_client.llen(config.prefix_cmd+init_host):
                raise Exception("%s should be null" % (config.prefix_cmd+init_host))
    
    
    def conn_localhost(self,listen_tag=config.local_ip_list):
        """
        对本地的操作不需要再使用连接
        """
        #进程自己创建连接池 单个进程内的线程共享
        redis_connect=None
        logger.debug("localhost start, listen on: %s" % str(listen_tag))
        lh=LocalHost([self.redis_send_config,self.redis_log_config],listen_tag,redis_connect=redis_connect) 
        lh.forever_run() 
        #阻塞运行，以下操作不应该被运行
        logger_err.error("localhost should not end, something error!")
        

    def is_host_alive(self,ip,lock=True):
        """
        判断SSH是否已经连接
        一个主机只能运行允许一个并发进行判断
        """

        check_flag=self.redis_send_client.get(config.prefix_check_flag+ip)
       
        #拿不到判断的flag则默认服务是连接的
        if check_flag:
            is_alive=True

        else:
            if lock:
                self.redis_send_client.set(config.prefix_check_flag+ip,1)
            
            if not self.redis_send_client.exists(config.prefix_heart_beat+ip):
                is_alive=False
            else:
                is_alive=True
                self.redis_send_client.delete(config.prefix_check_flag+ip)

        return is_alive
    
    
    def conn_host(self,init_host,redis_connect,init_host_uuid,proxy_mode=False):
        try:
            #如果连接存在 则不必再创建 否则则新建连接 
            if not self.is_host_alive(init_host):
                host_info=self.redis_config_client.hgetall(config.prefix_realhost+init_host)
                host_info["tag"]=host_info["ip"]
                host_info["ip"]=host_info["ip"].split("_")[0]
                          
                if proxy_mode and not ("proxy" in host_info and host_info["proxy"].strip()) :
                    self.redis_log_client.hset(init_host_uuid,"exit_code","init failed")
                    self.redis_log_client.hset(init_host_uuid,"stderr","proxy host error: %s" % init_host)    
                
                if not ("ip" in host_info): 
                    self.redis_log_client.hset(init_host_uuid,"exit_code","host info err")
                    logger_err.error("< %s > init failed, host info error, ip not exist" % init_host)
    
                elif not self.redis_send_client.llen(config.prefix_cmd+init_host):                
                        
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
            self.redis_log_client.hset(init_host_uuid,"exit_code","init failed")
            self.redis_log_client.hset(init_host_uuid,"stderr",format_exc())
            logger_err.error(format_exc())
    
    
    @connection_error_rerun()
    def __remot_host(self):
        """
        监听队列进行主机控制连接 与 关闭 
        只允许干净连接，即命令队列中不应该存在以前的旧命令

        """
        #redis_connect=self.redis_connect   #全部进程使用全局共享连接池
        #redis_connect=RedisConn()          #每个进程共享连接池       
        redis_connect=None                  #每个远程连接对象自己创建独占的连接池
        while True:
            
            init_host=self.redis_send_client.blpop(config.key_conn_control) 
            init_host_list=init_host[1].split(config.spliter)
            init_host=init_host_list[0].strip()
            if len(init_host_list)>1:
                init_host_uuid=init_host_list[1].strip()
            else:
                init_host_uuid=uuid.uuid1().hex

            #统一一个队列顺序实现创建、关闭 
            #避免同一个主机多次创建 同时存在关闭与创建
            try:
                #lstrip存在bug如 close_localhost
                close_tag=re.search("(?<=^"+config.pre_close+").*",init_host).group()
            except:
                close_tag=""
            host_info=self.redis_config_client.hgetall(config.prefix_realhost+init_host)
            
            if close_tag:
                #关闭
                #如 close_192.168.1.1 close_192.168.16.1_xxx
                #close_tag=init_host.lstrip(config.pre_close)                
                logger.debug("< %s > begin closing" % close_tag) 
                self.redis_send_client.publish(config.key_kill_host,close_tag) 
            
            elif not self.is_host_alive(init_host,False):
                #轻量级判断不用加锁
                
                if "proxy" in host_info and host_info["proxy"].strip():
                    proxy_list_name=config.proxy_tag+":"+host_info["proxy"].strip()
                    self.redis_send_client.rpush(proxy_list_name,init_host)
                    logger.debug("< %s > will init connect by proxy, not here" % init_host)
                
                elif init_host:
                    #启动 
                    self.conn_host(init_host,redis_connect,init_host_uuid)
                    
                else:
                    logger_err.error("do nothing on %s" % init_host)
            else:
                self.redis_log_client.hset(init_host_uuid,"stdout","connect exist,init skip")  
                logger.debug("< %s > init skipped" % init_host)    
             
    
    @connection_error_rerun()
    def __close_host(self):
        """
        主机自动关闭 
        在一段时间内没有任何操作后 log决定
        避免创建不久后被判断为要关闭
        将需要关闭的信息插入队列 由__remot_host执行关闭
        """
        hb_tag=config.prefix_heart_beat
        while True:
            
            for k in self.redis_send_client.keys(hb_tag+"*"):
                ip=k.lstrip(hb_tag)
                
                #logger.debug("< %s > auto check if should close connection." % ip )
                   
                if self.redis_send_client.exists(config.prefix_initing+ip):
                    #在一段时间之前刚启动 因此不要关闭
                    logger.debug("< %s > is init in near time,will not close" % ip)
                else:
                    close_flag=False
                    log_host_len=self.redis_log_client.llen(config.prefix_log_host+ip)                    
                    if log_host_len>0:
                        log_host_last=self.redis_log_client.lrange(config.prefix_log_host+ip,log_host_len-1,log_host_len-1)[0]           
                        log_host_last_dict=self.redis_log_client.hgetall(log_host_last) 
                        log_host_last_end = "end_timestamp" in log_host_last_dict
                        if log_host_last_end:
                            if (time.time()-float(log_host_last_dict["end_timestamp"]))>config.host_close_time:
                                #最后的执行时间距离现在超过指定时间，可关闭    
                                close_flag=True
                                logger.debug("< %s > has no execution for a long time,will close.last exection info: %s" % \
                                             (ip,str(log_host_last_dict)))
                        elif not log_host_last_dict:
                            #最后一次执行的key的日志已经不存在，说明已经很长时间没有执行 可关闭
                            close_flag=True
                            logger.debug("< %s > last log is empty,will close" % ip)
                        else:
                            #最后的执行时间距离现在没有超过指定时间或者还没有返回时间，不可关闭
                            close_flag=False
                    else:
                        #log_host_<ip>不存在，可关闭
                        close_flag=True
                        logger.debug("< %s > log empty,will close." % ip)

                    if close_flag:
                        self.redis_send_client.rpush(config.key_conn_control,config.pre_close+ip)
                    else:
                        logger.debug("< %s > will not close auto." % ip)
            
            time.sleep(config.host_close_check_interval)   
    
    
    def __real_job_exe(self,job_id):
        """
        单个任务的执行
        """       
 
        logger.info("start job %s" % job_id)
        job=self.redis_job_client.hgetall(job_id)

        log_job={}
        log_job["begin_timestamp"]=time.time()
        log_job["playbook"]=job["playbook"]
        playbook=job["playbook"]
        # 不为绝对路径时，以playbook目录为根目录
        # 在windows部署时只能使用相对路径
        #if not re.match("^/.*",playbook):
        playbook=os.path.join(config.base_dir,self.playbook_dir,playbook)
        log_job["playbook_rownum"]=file_row_count(playbook)
        log_job["playbook_md5"]=my_md5(file=playbook)
        
        log_target=[]
        for oc in job["target"].split(","):
            c=oc.split(config.spliter)[0]
            
            try: 
                cluster_id=oc.split(config.spliter)[1]    
            except:
                cluster_id=uuid.uuid1().hex
            
            new_c=c+config.spliter+cluster_id
            
            if self.redis_tmp_client.hgetall(new_c):    
                #在tmp库存在要执行的对象，则不必再从config库复制
                log_target.append([new_c,config.prefix_log_target+cluster_id])
            else:
                #需要复制但在config库中不存在，则跳到下一个循环
                log_target.append([new_c,config.prefix_log_target+cluster_id])
                if not self.redis_config_client.hgetall(c):
                    self.redis_log_client.hmset(config.prefix_sum+cluster_id,{"stop_str":"not exist"})
                    continue 
                
                #执行运行时对象复制一份，以确保原数据不影响其他并发
                #提前设置过期 防止运行到一半失败时一直占用 
                self.redis_tmp_client.hmset(new_c,self.redis_config_client.hgetall(c))
                self.redis_tmp_client.expire(new_c,config.tmp_config_expire_sec)
           
            #session在生成job时已经放入tmp库
            #有些任务可能没有session
            try:
                s=job[config.prefix_session]
                self.redis_tmp_client.hset(new_c,config.prefix_session,s)
            except:
                pass
            
            try:
                
                #ce=ClusterExecution(cluster_id,self.redis_config_list,self.redis_connect)     #使用共享连接池会导致在redis重连时有一定概率出错 why？
                ce=ClusterExecution(cluster_id,self.redis_config_list)
                
                if "begin_line" in job:
                    begin_line=int(job["begin_line"])
                else:
                    begin_line=0
                
                ce.run(new_c,playbook,begin_line)
            except:
                self.redis_tmp_client.expire(new_c,config.tmp_config_expire_sec)
                self.redis_log_client.hmset(config.prefix_sum+cluster_id,{"stop_str":"runing failed"})
                logger_err.error("could not use playbook on %s" % c )
                logger_err.error(format_exc())
        
        log_job["log"]=str(log_target)
        self.redis_log_client.hmset(config.prefix_log_job+job_id.split(config.prefix_job)[1],log_job)        
    
    
    def __job_exe(self):
        """
        监听队列持续执行任务
        任务执行 select 0;   hset job_xxxxxx;   rpush job_list job_xxx
        任务终止 select 0;   kill_xxxxxx
        {'target': 'cluster1,cluster2,cluster3', 'job_id': 'ccc', 'playbook': '/root/test4/a.txt','session':'session_xxxx'}  
        session为可选

        """
        while True:
            job_id=None
            try:
                job_id=self.redis_send_client.blpop(config.key_job_list)     #redis重新连接运行会有连接报错
                job_id=job_id[1]
            except:
                try:
                    job_id=self.redis_send_client.lpop(config.key_job_list)
                except:
                    #logger_err.debug(format_exc())
                    time.sleep(5)
                
            if job_id:
                t=Thread(target=self.__real_job_exe,args=(job_id,))
                t.start()    
    
    
    def run_forever(self):
        """
        使用多进程/多线程
        conn_localhost 本地执行
        __remot_host 远程连接创建
        __job_exe    执行任务 创建ClusterExecution实例，循环监听队列，运行playbook
        __close_host 判定是否自动关闭远程连接
        """
        self.is_listen_tag_clean()
        
        #这两个任务压力不大，使用线程即可
        t1=Thread(target=self.__job_exe)        
        t2=Thread(target=self.__close_host)
        t1.start()
        t2.start()
        
        p_list=[]
        
        p1=Process(target=self.conn_localhost)
        p_list.append(p1)
        
        #远程主机众多时需要使用多进程分担，充分利用cpu
        #for i in range(3):
        for i in range(config.remote_process):
            p2=Process(target=self.__remot_host)
            p_list.append(p2)
        
        self.process_run(p_list,redis_client=self.redis_send_client)
        
        return p_list
    
    
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
        