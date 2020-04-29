#coding:utf8
import uuid
import time
import sys
if sys.version_info>(3,0):
    import queue as Queue
else:
    import Queue
from threading import Thread
import subprocess
from traceback import format_exc

from lib.wrapper import gen_background_log_set,connection_error_rerun
from lib.logger import logger,logger_err
from lib.utils import get_host_ip
from lib.redis_conn import RedisConn
from conf import config



class LocalHost(object):
    """
    对本地的执行
    """
    def __init__(self,redis_config_list,listen_tag,t_number=5):
        self.redis_send_client=None
        self.redis_log_client=None
        
        self.redis_send_config=redis_config_list[0]
        self.redis_log_config=redis_config_list[1]
        self.redis_init()
        
        #127.0.0.1 localhost
        #proxy:10.0.0.1:127.0.0.1 proxy:10.0.0.1:localhost
        self.listen_tag=listen_tag
        #self.tag=self.listen_tag[0]
    
        self.thread_q=Queue.Queue(t_number)   #单个主机的并发
    
    
    def redis_init(self):
        """
        redis断开后的重连
        """
        rc=RedisConn()        
        self.redis_send_client=rc.refresh(self.redis_send_client,self.redis_send_config)
        self.redis_log_client=rc.refresh(self.redis_log_client,self.redis_log_config)
        
    
    @connection_error_rerun()
    def __heart_beat(self):
        """
        心跳
        """
        self.redis_init()
        while True:
            for tag in self.listen_tag:
                self.redis_send_client.set(config.prefix_heart_beat+tag,time.time())
                self.redis_send_client.expire(config.prefix_heart_beat+tag,config.host_check_success_time)
            
            time.sleep(config.heart_beat_interval)
                
            
    def __single_run(self,cmd,cmd_uuid,tag):
        """
        本地执行只支持cmd命令
        不能使用扩展的PUT/GET命令
        """
        exe_result={}
        exe_result["begin_timestamp"]=time.time()
        exe_result["cmd"]=cmd
        exe_result["uuid"]=cmd_uuid
        exe_result["exe_host"]=tag
        exe_result["from_host"]=get_host_ip()
        exe_result["cmd_type"]="CMD"
        self.set_log(tag,exe_result,is_update=False)
        logger.debug(str(exe_result)+" begin")
        stdout,stderr="",""
        try:
            """
            c=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            stdout,stderr=c.communicate()
            exit_code=c.returncode
            """
            p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
            
            background_log_set=gen_background_log_set(cmd_uuid,self.redis_log_client)
            
            stdout,stderr = background_log_set(p.stdout,p.stderr)
                        
            p.communicate()
            exit_code=p.returncode
            
        except:
            logger_err.error(format_exc())
            stdout, stderr, exit_code="","some error happen when execute,please check the log",1
        
        exe_result["stdout"]=stdout
        exe_result["stderr"]=stderr
        exe_result["exit_code"]=exit_code  
        exe_result["end_timestamp"]=time.time()
        
        self.set_log(tag,exe_result,is_update=True)
        logger.debug(str(exe_result)+" done")
        
        self.thread_q.get()          #停止阻塞下一个线程   
    
    
    @connection_error_rerun()
    def __forever_run(self,tag):
        """
        无限接收命令
        """
        self.redis_init()
        key = config.prefix_cmd + tag
        while True:
            self.thread_q.put(1)                #控制并发数
            try:
                #使用阻塞获取 好处是能及时响应 
                t_allcmd=self.redis_send_client.blpop(key)                   
            except :
                #如果获取出现则需要先移除已经占用的队列，防止队列处于满的状态
                self.thread_q.get()
                raise

            if t_allcmd:                           
                allcmd=t_allcmd[1]
                
                if allcmd:
                    allcmd=allcmd.split(config.spliter)        
                    cmd=allcmd[0].strip()
                    if len(allcmd)>1:
                        cmd_uuid=allcmd[1]
                    else:
                        cmd_uuid=uuid.uuid1().hex
                    
                    t=Thread(target=self.__single_run,args=(cmd,cmd_uuid,tag))
                    t.start()
                          
                else:
                    #命令为空时释放队列
                    self.thread_q.get()

            else:
                #命令为空时释放队列
                self.thread_q.get()    
    
    @connection_error_rerun()
    def set_log(self,tag,exe_result,is_update=True):
        """
        设置日志
        """
        log_uuid=exe_result["uuid"]
        if is_update:
            self.redis_log_client.expire(log_uuid,config.cmd_log_expire_sec)      #获取返回值后设置日志过期时间
        else:
            self.redis_log_client.rpush(config.prefix_log_host+tag,log_uuid)
        self.redis_log_client.hmset(log_uuid,exe_result)
    
    
    def forever_run(self):
        t1=Thread(target=self.__heart_beat)
        t_list=[t1]
        for k in self.listen_tag:
            t=Thread(target=self.__forever_run,args=(k,))
            t_list.append(t)
        
        for t in t_list:
            t.start()
        
        for t in t_list:
            t.join()
