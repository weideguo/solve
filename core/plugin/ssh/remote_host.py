# -*- coding: utf-8 -*-
import os
import re
import uuid
import time
import sys
if sys.version_info>(3,0):
    import queue as Queue
else:
    import Queue
from threading import Thread
from traceback import format_exc

from lib.redis_conn import RedisConn
from lib.wrapper import logger,logger_err
from lib.myssh import MySSH
from lib.password import Password

from core.abstract.abstract_host import AbstractHost

from conf import config


password=Password(aes_key=config.aes_key)


class RemoteHost(MySSH, AbstractHost):
    """
    SSH远程连接类
    在远端执行命令 上传下载文件
    持续监听队列获取命令
    续监听队列判断是否关闭连接
    
    只确保当前正在执行的能正确返回 不必维护执行队列
    """
    
    def __init__(self,host_info,redis_config_list,t_number=config.max_concurrent_thread,redis_connect=None):
        
        host_info["passwd"] = password.decrypt(str(host_info.get("passwd","")))
        
        super(RemoteHost, self).__init__(host_info)       
        
        self.ip =host_info["ip"]
        self.tag=host_info.get("tag") or self.ip
        
        self.cmd_key       = config.prefix_cmd+self.tag
        self.heartbeat_key = config.prefix_heart_beat+self.tag
        self.cloing_key    = config.prefix_closing+self.tag
        
        self.redis_send_config=redis_config_list[0]
        self.redis_log_config=redis_config_list[1]
        
        if redis_connect:
            rc=redis_connect                                                        #单个进程所创建的远程连接共享连接池  redis连接被多个远程连接复用
            self.is_disconnect=False                                                #关闭远程连接不能回收redis连接
        else:
            rc=RedisConn(max_connections=config.remote_host_redis_pool_size)        #每个远程连接使用自己的连接池  有些连接不能被共享  如进行blpop操作时/消息订阅时 因而在此需要大于2
            self.is_disconnect=True                                                 #在关闭远程连接时回收redis连接

        self.redis_send_client=rc.refresh(self.redis_send_config)
        self.redis_log_client=rc.refresh(self.redis_log_config) 
        
        self.redis_client_list=[self.redis_send_client,self.redis_log_client]
        
        self.thread_q=Queue.Queue(t_number)   #单个主机的并发
        self.t_thread_q=Queue.Queue(t_number) #用于存储正在运行的队列 
        self.is_run=False                     #后台运行    
    
       
    def init_conn(self):
        """
        初始化连接
        """
        super(RemoteHost, self).init_conn()
        
        self.is_run=True
    
     
    def __single_run(self,cmd,cmd_uuid):
        """
        线程控制的单个命令的执行
        """
        try:
            self.single_run(cmd,cmd_uuid,self.tag)
        except:
            logger_err.error(format_exc())
        self.thread_q.get()                                   #停止阻塞下一个线程            
    
    
    def __forever_run(self):
        """
        持续监听由redis队列获取命令
        通过线程开启并发操作 
        """

        #key=config.prefix_cmd+self.tag
        while self.is_run:
            self.thread_q.put(1)                #控制并发数 放在此控制可以避免命令队列被提前消耗
            try:    
                t_allcmd=self.redis_send_client.blpop(self.cmd_key)    
                #使用阻塞获取 好处是能及时响应 
            except:
                #redis连接失败立即关闭命令监听
                break
            
            if t_allcmd:                           
                allcmd=t_allcmd[1]
                #阻塞的过程中连接可能已经被关闭 所以需要再次判断
                if not self.is_run:
                    #self.redis_send_client.lpush(self.cmd_key,allcmd)        #不必维护未执行队列          
                    #logger.debug("will not exe %s" % allcmd)
                    allcmd=""

                if allcmd:
                    allcmd=allcmd.split(config.spliter)        
                    cmd=allcmd[0]
                    if len(allcmd)>1:
                        cmd_uuid=allcmd[1]
                    else:
                        cmd_uuid=uuid.uuid1().hex
                    
                    t=Thread(target=self.__single_run,args=(cmd,cmd_uuid))
                    t.start()
                    
                    if self.t_thread_q.full():
                        self.t_thread_q.get()
                    self.t_thread_q.put(t)            
                else:
                    #命令为空时释放队列
                    self.thread_q.get()

            else:
                #命令为空时释放队列
                self.thread_q.get()
        
    
    def __heart_beat(self):
        """
        定时更新连接信息
        """
        try:
            while self.is_run:
                logger.debug("%s heart beat" % self.tag)
                self.redis_send_client.set(self.heartbeat_key,time.time())
                #断开后key自动删除
                self.redis_send_client.expire(self.heartbeat_key,config.host_check_success_time)
                time.sleep(config.heart_beat_interval)
                
            self.redis_send_client.delete(self.heartbeat_key) 
        except:
            pass
        
    
    def __close_conn(self):
        """
        判断是否关闭 
        """
        #使用订阅阻塞获取需要kill的ip 
        pub=self.redis_send_client.pubsub()
        pub.psubscribe(config.key_kill_host)
        while True:             
            pub.listen()
            try:
                kill_info=pub.parse_response(block=True) 
            except:
                break
            
            kill_tag=kill_info[-1]

            if kill_tag==self.tag:            
                break
        
        self.is_run=False       
        try:
            self.redis_send_client.set(self.cloing_key,time.time())    #标记host处于关闭状态，不再执行新命令
        except:
            pass
        
        #等待后台的并发运行执行结束
        while not self.t_thread_q.empty():
            t=self.t_thread_q.get()
            t.join()
        
        try:
            #self.ftp_client.close()
            self.ssh_client.close()
        except:
            pass
        
        logger.info("%s is closed" % self.tag)        
        
        #关闭订阅连接 其他线程才能从线程池获取连接客户端
        pub.close()
        
        #self.thread_q.put(1,0)
        if not self.redis_send_client.llen(self.cmd_key):
            #用于释放阻塞
            self.redis_send_client.rpush(self.cmd_key,"")
        
        self.redis_send_client.delete(self.heartbeat_key)
        self.redis_send_client.expire(self.cloing_key,config.closing_host_flag_expire_sec)    
        self.redis_send_client.delete(self.cmd_key)          #清空未执行的队列防止启动时错误地运行
        
        if self.is_disconnect:
            #释放连接 防止连接数一直增大
            for client in [self.redis_client_list]:
                try:
                    client.connection_pool.disconnect()
                except:
                    pass
        
    
    #重载提供给上层的入口函数
    def forever_run(self):
        """
        非阻塞后台运行        
        """
        try:
            self.init_conn()
        except BaseException:
            logger_err.error(format_exc())
            raise BaseException
        else:
            t1=Thread(target=self.__forever_run)
            t2=Thread(target=self.__heart_beat)
            t3=Thread(target=self.__close_conn)
            
            for t in [t1,t2,t3]:
                t.start()    
    
