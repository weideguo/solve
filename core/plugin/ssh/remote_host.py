#coding:utf8
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

import redis

from lib.logger import logger,logger_err
from lib.utils import my_md5,get_host_ip
from lib.myssh import MySSH
from conf import config



class RemoteHost(MySSH):
    """
    SSH远程连接类
    在远端执行命令 上传下载文件
    持续监听队列获取命令
    续监听队列判断是否关闭连接
    """
    
    def __init__(self,host_info,redis_send_pool,redis_log_pool,t_number=config.max_concurrent_thread):
    
        #super(RemoteHost, self).__init__(host_info)
        super(RemoteHost, self).__init__(host_info)       
 
        self.ip=host_info["ip"]
        if "tag" in host_info:
            self.tag=host_info["tag"]
        else:
            self.tag=self.ip
 
        self.redis_send_pool=redis_send_pool
        self.redis_log_pool=redis_log_pool
        self.redis_send_client=None
        self.redis_log_client=None

        self.thread_q=Queue.Queue(t_number)   #单个主机的并发
        self.t_thread_q=Queue.Queue(t_number) #用于存储正在运行的队列 
        self.is_run=False                     #后台运行    
    
    
    def init_conn(self):
        """
        初始化连接
        """
        super(RemoteHost, self).init_conn()
        
        self.redis_send_client=redis.StrictRedis(connection_pool=self.redis_send_pool)
        self.redis_log_client=redis.StrictRedis(connection_pool=self.redis_log_pool)
        self.is_run=True
            
    
    def send_file(self,local_file,remote_path,c_uuid,set_info):
        """
        从本地上传文件到远端 文件名不变
        远端目录如果不存在 则创建一个
        远端文件如果存在 则使用时间戳重命名远端文件
        """
        if not os.path.isfile(local_file):
            return "","",0,"local file not exist"        

        file_name=os.path.basename(local_file)
        remote_file=os.path.join(remote_path,file_name)

        local_md5=my_md5(file=local_file)
        local_filesize=os.path.getsize(local_file)
        
        put_flag = False
        if self.redis_log_client.hexists(config.prefix_put+self.tag,local_md5):
            #已经存在其他上传操作的情况
            wait_flag = 1 
            while wait_flag:
                exist_remote_file = self.redis_log_client.hget(config.prefix_put+self.tag,local_md5)
                if exist_remote_file:
                    wait_flag = 0
                    try:
                        self.redis_log_client.hset(c_uuid,"remote_md5","copying")
                        remote_md5,local_md5,is_success,error_msg=self.copy_file(exist_remote_file,remote_file,set_info,local_md5,\
                                                                                local_filesize,config.is_copy_by_link)
                        if is_success:
                            return remote_md5,local_md5,is_success,error_msg
                        else:
                            logger_err.debug("copy but faild:  %s %s %s %s" % (remote_md5,local_md5,is_success,error_msg))   
                            put_flag = True
                    except:
                        logger_err.debug(format_exc())
                        return "","",0,"copy remote file failed"
                    
                else:
                    #如果其他上传还在进行 则等待后再检查
                    self.redis_log_client.hset(c_uuid,"remote_md5","waiting others complete:"+str(wait_flag))
                    time.sleep(config.put_wait_time)
                    #超时检查
                    wait_flag = wait_flag+1                                       
                    if wait_flag> config.put_wait:
                        wait_flag=0
                        put_flag = True
        else:
            #没有其他上传操作
            put_flag = True

        if put_flag:
            self.redis_log_client.hset(config.prefix_put+self.tag,local_md5,"")
            try:
                local_md5,remote_md5,is_success,error_msg=self.put_file(local_file,remote_path,set_info)
                if is_success:
                    self.redis_log_client.hset(config.prefix_put+self.tag,local_md5,remote_file)
                else:
                    self.redis_log_client.hdel(config.prefix_put+self.tag,local_md5)
                    
                return local_md5,remote_md5,is_success,error_msg
            except:
                self.redis_log_client.hdel(config.prefix_put+self.tag,local_md5)
                logger_err.error(format_exc())
                return "","",0,"upload failed"
        else:
            return "","",0,"some thing error in upload"
    
    def set_info_gen(self,cmd_uuid):
        #函数生成
        def set_info(current_size,total_size):
            """
            上传下载的回调函数 只能同时存在一个上传或下载操作 否则回调调用出错
            """
            self.redis_log_client.hset(cmd_uuid,"current_size",current_size)
            self.redis_log_client.hset(cmd_uuid,"total_size",total_size)
        return set_info

    
    def __single_run(self,cmd,cmd_uuid):
        """
        单个命令的执行
        """
        #logger.debug("----------------------------------")

        exe_result={}

        begin_timestamp=time.time()
        exe_result["begin_timestamp"]=begin_timestamp
        exe_result["cmd"]=cmd
        exe_result["uuid"]=cmd_uuid
        exe_result["exe_host"]=self.tag
        exe_result["from_host"]=get_host_ip(self.ip)
        
        logger.debug(str(exe_result)+" begin")
        
        try:
            #上传文件的cmd PUT:/local_path/file_name:/remote_path
            #下载文件的cmd GET:/local_path/file_name:/remote_path
            if re.match("PUT:.+?:.+?",cmd) or re.match("GET:.+?:.+?",cmd):                      
                cmd_type=cmd.split(":")[0]
                exe_result["cmd_type"]=cmd_type            
                self.set_log(exe_result,is_update=False)      #命令执行前   

                if cmd_type=="PUT":
                    file_flag,local_file,remote_path=cmd.split(":")
                    remote_path=remote_path.rstrip()
                    
                    local_md5,remote_md5,is_success,msg=self.send_file(local_file,remote_path,exe_result["uuid"],self.set_info_gen(cmd_uuid))
                    
                elif cmd_type=="GET":
                    file_flag,local_path,remote_file=cmd.split(":") 
                    remote_file=remote_file.rstrip()
                    
                    local_md5,remote_md5,is_success,msg=self.get_file(local_path,remote_file,self.set_info_gen(cmd_uuid))
                
                exe_result["local_md5"]=local_md5
                exe_result["remote_md5"]=remote_md5
                exe_result["is_success"]=int(is_success)
                
                if is_success:
                    stdout=msg
                    stderr=""
                else:
                    stdout=""
                    stderr=msg
                exit_code=int(not is_success) 

            else:
                cmd_type="CMD"
                exe_result["cmd_type"]=cmd_type
                self.set_log(exe_result,is_update=False)      #命令执行前                   

                stdout, stderr, exit_code=self.exe_cmd(cmd)
        except:
            logger_err.error(format_exc())
            stdout, stderr, exit_code="","some error happen when execute,please check the log",1

        exe_result["stdout"]=stdout
        exe_result["stderr"]=stderr
        exe_result["exit_code"]=exit_code   

        exe_result["end_timestamp"]=time.time()

        self.set_log(exe_result)               #命令执行完毕后更新日志

        logger.debug(str(exe_result)+" done")
        #logger.debug("----------------------------------")

        self.thread_q.get()                                   #停止阻塞下一个线程            
            
 

    def set_log(self,exe_result,is_update=True):
        """
        设置日志
        """
        log_uuid=exe_result["uuid"]
        if is_update:
            self.redis_log_client.expire(log_uuid,config.cmd_log_expire_sec)      #获取返回值后设置日志过期时间
        else:
            self.redis_log_client.rpush(config.prefix_log_host+self.tag,log_uuid)
        self.redis_log_client.hmset(log_uuid,exe_result)

   
    def __forever_run(self):
        """
        持续监听由redis队列获取命令
        通过线程开启并发操作 
        """

        key=config.prefix_cmd+self.tag

        while self.is_run:
            self.thread_q.put(1)                #控制并发数
            t_allcmd=self.redis_send_client.blpop(key,1)       
            #使用阻塞获取 好处是能及时响应 

            if t_allcmd:                           
                allcmd=t_allcmd[1]
                #阻塞的过程中连接可能已经被关闭 所以需要再次判断
                if not self.is_run:
                    self.redis_send_client.lpush(key,allcmd)               
                    #logger.debug("will not exe %s" % allcmd)
                    allcmd=""

                if allcmd:
                    allcmd=allcmd.split(config.spliter)        
                    cmd=allcmd[0]
                    if len(allcmd)>1:
                        cmd_uuid=allcmd[1]
                    else:
                        cmd_uuid=uuid.uuid1().hex

                    #self.thread_q.put(1)                #控制并发数

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
        while self.is_run:
            logger.debug("%s heart beat" % self.tag)
            self.redis_send_client.set(config.prefix_heart_beat+self.tag,time.time())
            #断开后key自动删除
            self.redis_send_client.expire(config.prefix_heart_beat+self.tag,config.host_check_success_time)
            time.sleep(config.heart_beat_interval)

        self.redis_send_client.delete(config.prefix_heart_beat+self.tag)
        
    
    def __close_conn(self):
        """
        判断是否关闭 
        """
        #使用订阅阻塞获取需要kill的ip 
        pub=self.redis_send_client.pubsub()
        pub.psubscribe(config.key_kill_host)
        while True:             
            pub.listen()
            kill_info=pub.parse_response(block=True)     #阻塞获取
            kill_tag=kill_info[-1]

            if kill_tag==self.tag:            
                self.is_run=False
                self.redis_send_client.set(config.prefix_closing+self.tag,time.time())    #标记host处于关闭状态，不再执行新命令
                #正在运行的并发运行完毕后再退出
                while not self.t_thread_q.empty():
                    t=self.t_thread_q.get()
                    t.join()

                self.close()
                break

        self.redis_send_client.delete(config.prefix_heart_beat+self.tag)
        self.redis_send_client.expire(config.prefix_closing+self.tag,config.closing_host_flag_expire_sec)      #关闭已经完成  
    

    def close(self):
        """
        不再执行之后的命令 但当前正在执行的命令还是会后台运行
        """
        #self.ftp_client.close()
        self.ssh_client.close()
        self.is_run=False
        #self.redis_send_client=None            #不重置以确保redis还能用于重置命令队列 
        #self.redis_log_client=None        

        logger.info("%s is closed" % self.tag)



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
            t1.start()

            t2=Thread(target=self.__heart_beat)
            t2.start()

            t3=Thread(target=self.__close_conn)
            t3.start()    
    
