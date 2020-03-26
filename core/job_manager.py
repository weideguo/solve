#coding:utf8

import re
import time
import uuid
from threading import Thread
from multiprocessing import Process
from traceback import format_exc

import redis

from .localhost import LocalHost
from .cluster_exe import ClusterExecution
from lib.utils import my_md5,file_row_count
from lib.logger import logger,logger_err
from conf import config


import importlib


class_name = config.remote_model.split(".")[-1]
module_name = ".".join(config.remote_model.split(".")[:-1])
mod = importlib.import_module(module_name)
RemoteHost = getattr(mod, class_name)


class JobManager():
    """
    任务执行管理类
    持续监听redis队列获取任务并执行
    SSH连接与关闭的控制
    """    

    def __init__(self,redis_send_pool,redis_log_pool,redis_tmp_pool,redis_job_pool,redis_config_pool):

        self.redis_send_pool=redis_send_pool
        self.redis_log_pool=redis_log_pool
        self.redis_tmp_pool=redis_tmp_pool
        self.redis_job_pool=redis_job_pool        
        self.redis_config_pool=redis_config_pool
        
        self.redis_send_client=redis.StrictRedis(connection_pool=redis_send_pool)    
        self.redis_log_client=redis.StrictRedis(connection_pool=redis_log_pool)
        self.redis_job_client=redis.StrictRedis(connection_pool=redis_job_pool)
        self.redis_tmp_client=redis.StrictRedis(connection_pool=redis_tmp_pool)
        self.redis_config_client=redis.StrictRedis(connection_pool=redis_config_pool)
        
    
    def is_listen_tag_clean(self,listen_tag=config.local_ip_list):
        #启动本地时检查是否已经存在旧的命令
        for init_host in listen_tag:
            if self.redis_send_client.llen(config.prefix_cmd+init_host):
                raise Exception("%s should be null" % (config.prefix_cmd+init_host))
    
    
    def conn_localhost(self,listen_tag=config.local_ip_list,check=False):
        """
        对本地的操作不需要再使用连接
        """
        
        if check:
            self.is_listen_tag_clean()
        
        logger.debug("localhost start")
        lh=LocalHost(self.redis_send_pool,self.redis_log_pool,listen_tag) 
        lh.forever_run() 
        #阻塞运行，以下操作不应该被运行
        logger_err.error("localhost should not end, something error!")
        

    def is_host_alive(self,ip):
        """
        判断SSH是否已经连接
        一个主机只能运行允许一个并发进行判断
        """

        check_flag=self.redis_send_client.get(config.prefix_check_flag+ip)
       
        #拿不到判断的flag则默认服务是连接的
        if check_flag:
            is_alive=True

        else:
            self.redis_send_client.set(config.prefix_check_flag+ip,1)
            if not self.redis_send_client.exists(config.prefix_heart_beat+ip):
                is_alive=False
            else:
                is_alive=True
                self.redis_send_client.delete(config.prefix_check_flag+ip)

        return is_alive
    
    
    def conn_host(self,init_host,init_host_uuid):
        #如果连接存在 则不必再创建 否则则新建连接 
        if not self.is_host_alive(init_host):
            host_info=self.redis_config_client.hgetall(config.prefix_realhost+init_host)
            if not ("ip" in host_info): 
                self.redis_log_client.hset(init_host_uuid,"exit_code","host info err")
                logger_err.error("< %s > init failed, host info error, ip not exist" % init_host)

            elif not self.redis_send_client.llen(config.prefix_cmd+init_host):                
                    
                logger.debug("init host info %s" % str(host_info))
        
                try:
                    self.redis_send_client.set(config.prefix_initing+init_host,time.time())
                    h=RemoteHost(host_info,self.redis_send_pool,self.redis_log_pool)
                    h.forever_run()
                    logger.info("< %s > init success" % init_host)                    
                except:
                    self.redis_log_client.hset(init_host_uuid,"exit_code","init failed")
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
  
  
    def __remot_host(self):
        """
        监听队列进行主机控制连接 与 关闭 
        只允许干净连接，即命令队列中不应该存在以前的旧命令

        """

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
            if re.match(config.pre_close+".*",init_host):
                #关闭
                #如 close_192.168.1.1 close_PROXY:10.0.0.1:192.168.16.1
                close_tag=init_host.lstrip(config.pre_close)                
                logger.debug("< %s > begin closing" % close_tag) 
                self.redis_send_client.publish(config.key_kill_host,close_tag) 

            elif re.match("^PROXY:"+".*",init_host.upper()):
                # PROXY 如 PROXY:10.0.0.1:192.168.16.1  不分大小写
                # 不在本地创建连接，由其他proxy创建链接
                # 广播让其他proxy接收
                self.redis_send_client.publish(config.proxy_tag,init_host) 
                logger.debug("< %s > will init connect by proxy, not here" % init_host)
            
            elif (init_host in config.local_ip_list):
                # 为localhost 或 127.0.0.1
                # 不在创建连接，由本地执行策略执行
                logger.debug("< %s > run in local mode" % init_host)
                
            elif init_host:
                #启动 
                self.conn_host(init_host,init_host_uuid)

            else:
                logger_err.error("do nothing on %s" % init_host)
    

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
                            #后的执行时间距离现在没有超过指定时间或者还没有返回时间，不可关闭
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
        log_job["playbook_rownum"]=file_row_count(job["playbook"])
        log_job["playbook_md5"]=my_md5(file=job["playbook"])
        
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
                
                ce=ClusterExecution(self.redis_send_pool,self.redis_log_pool,self.redis_tmp_pool,self.redis_config_pool)
                
                if "begin_line" in job:
                    begin_line=int(job["begin_line"])
                else:
                    begin_line=0
                
                ce.run(new_c,job["playbook"],cluster_id,begin_line)
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
            job_id=self.redis_send_client.blpop(config.key_job_list)
            job_id=job_id[1]
            t=Thread(target=self.__real_job_exe,args=(job_id,))
            t.start()
    
    
    def __remote_host_manage(self):
        """
        用于ssh连接的后台管理进程
        __remot_host 远程连接创建
        __job_exe    执行任务 创建ClusterExecution实例，循环监听队列，运行playbook
        __close_host 判定是否自动关闭远程连接
        """
        t1=Thread(target=self.__remot_host)
        t2=Thread(target=self.__job_exe)
        t3=Thread(target=self.__close_host)
        
        t1.start()
        t2.start()
        t3.start()
        
        t1.join()
        t2.join()
        t3.join() 
        
    
    def run_forever(self):
        """
        使用多进程
        一个进程用于ssh 任务管理等
        一个进程用于本地执行
        """
        self.is_listen_tag_clean()
        
        p1=Process(target=self.__remote_host_manage)
        p2=Process(target=self.conn_localhost)
        
        p1.start()
        p2.start()
        
        #获取当前进程的pid
        #os.getpid()
        #使用redis保存子进程的pid
        for pid in [p1.pid,p2.pid]:
            self.redis_send_client.rpush("__pid__",pid)
        
        p1.join()
        p2.join()
        
        