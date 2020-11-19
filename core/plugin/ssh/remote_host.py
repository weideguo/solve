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
from lib.wrapper import gen_background_log_set,connection_error_rerun
from lib.logger import logger,logger_err
from lib.utils import my_md5,get_host_ip,cmd_split
from lib.myssh import MySSH
from lib.password import Password
from conf import config


password=Password(aes_key=config.aes_key)


class RemoteHost(MySSH):
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
        
        self.ip=host_info["ip"]
        if "tag" in host_info:
            self.tag=host_info["tag"]
        else:
            self.tag=self.ip
        
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
    
    
    def gen_set_step(self,cmd_uuid,name="step"):
        """
        生成设置步骤记录的函数
        如操作中可能有多个步骤，可以任意记录
        """
        def set_step(step="",name=name):
            self.redis_log_client.hset(cmd_uuid,name,step)
        return set_step
    
    
    def send_file(self,local_file,remote_path,set_info,set_step):
        """
        从本地上传文件到远端 文件名不变
        远端目录如果不存在 则创建一个
        远端文件如果存在 则使用时间戳重命名远端文件
        """
        if not os.path.isfile(local_file):
            return "","",0,"local file not exist"        

        file_name=os.path.basename(local_file)
        remote_file=os.path.join(remote_path,file_name)
        
        set_step("calculate local md5 begin")
        local_md5=my_md5(file=local_file)
        set_step("calculate local md5 done")
        local_filesize=os.path.getsize(local_file)
        
        put_flag = True     #是否要实际上传
        if self.redis_log_client.hexists(config.prefix_put+self.tag,local_md5):
            #已经存在其他上传操作的情况
            wait_flag = 1 
        else:
            wait_flag = 0
        
        #可以在等待过程中删除标记结束等待
        while wait_flag and self.redis_log_client.hexists(config.prefix_put+self.tag,local_md5):
            exist_remote_file = self.redis_log_client.hget(config.prefix_put+self.tag,local_md5)
            if exist_remote_file:
                #远端已经存在文件
                wait_flag = 0
                try:
                    set_step("copying","remote_md5")
                    #校验MD5并复制文件
                    remote_md5,local_md5,is_success,error_msg=self.copy_file(exist_remote_file,remote_file,local_md5,\
                                                                            local_filesize,config.is_copy_by_link,set_info,set_step)
                    if is_success:
                        return remote_md5,local_md5,is_success,error_msg
                    else:
                        logger.debug("copy but faild:  %s %s %s %s" % (remote_md5,local_md5,is_success,error_msg))   
                        set_step(error_msg+", copy failed, will upload","remote_md5")
                        #复制已经存在的文件失败 需要实际上传
                        put_flag = True
                except:
                    logger_err.debug(format_exc())
                    return "","",0,"copy remote file failed"
                
            else:
                #如果其他上传还在进行 则等待后再检查
                set_step("waiting others complete:"+str(wait_flag),"remote_md5")
                time.sleep(config.put_wait_time)
                #超时检查
                wait_flag = wait_flag+1                                       
                if wait_flag> config.put_wait:
                    wait_flag=0
                    #等待其他的上传超时 需要实际上传
                    put_flag = True
        

        if put_flag:
            self.redis_log_client.hset(config.prefix_put+self.tag,local_md5,"")
            try:
                local_md5,remote_md5,is_success,error_msg=self.put_file(local_md5,local_file,remote_path,set_info,set_step)
                #redis断开即导致上传失败 无需确保日志回写
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
    
    
    def gen_set_info(self,cmd_uuid):
        """生成用于上传时设置日志的函数"""
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
            #扩展命令以 "__"包围前后 使用格式如下
            #cmd="__xxx__ ..."
            #cmd=" __xxx__ ..."
            if re.match("\s*__\w+__($|\s)",cmd):
                exe_result,stdout,stderr,exit_code=self.__exe_extend(cmd, exe_result)

            else:
                cmd_type="CMD"
                exe_result["cmd_type"]=cmd_type
                self.set_log(exe_result,is_update=False)      #命令执行前                   

                stdout, stderr, exit_code=self.exe_cmd(cmd,background_log_set=gen_background_log_set(cmd_uuid,self.redis_log_client))
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
    
    
    def __exe_extend(self, cmd_line, exe_result):
        """
        执行自定义的扩展命令
        格式类似于shell命令即 
        cmd arg1 arg2 ...
        """
        exe_result["cmd_type"]="EXTEND"               
        self.set_log(exe_result,is_update=False)  
        
        cmd_uuid=exe_result["uuid"]
            
        try:    
            #不能存在多余的空格
            _cmd = cmd_split(cmd_line)
        except:
            stdout=""
            stderr="parse cmd line error"
            exit_code="1"                
            return exe_result,stdout,stderr,exit_code
            
        cmd  = _cmd[0]
        args = _cmd[1:]
                
        if cmd=="__put__":
            #上传文件的cmd 
            #__put__ /local_path/file_name /remote_path
            local_file,remote_path = args[0],args[1]
            remote_path=remote_path.rstrip()
            
            local_md5,remote_md5,is_success,msg=self.send_file(local_file,remote_path,self.gen_set_info(cmd_uuid),self.gen_set_step(cmd_uuid))
            
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
            
         
        elif cmd=="__get__":
            #下载文件的cmd 
            #__get__ /remote_path/file_name /local_path
            remote_file,local_path = args[0],args[1]
            remote_file=remote_file.rstrip()
            
            local_md5,remote_md5,is_success,msg=self.get_file(local_path,remote_file,self.gen_set_info(cmd_uuid),self.gen_set_step(cmd_uuid))
        
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
            #未实现的命令
            stdout=""
            stderr="extend command [%s]  not define" % cmd
            exit_code="127"               

        return exe_result,stdout,stderr,exit_code
        
    
    #确保当前执行的命令日志正确返回
    @connection_error_rerun()
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
                self.is_run=False
                try:
                    self.redis_send_client.set(self.cloing_key,time.time())    #标记host处于关闭状态，不再执行新命令
                except:
                    pass
                break
                
        #等待后台的并发运行执行结束
        while not self.t_thread_q.empty():
            t=self.t_thread_q.get()
            t.join()
           
        self.close()
        #关闭订阅连接 其他线程才能从线程池获取连接客户端
        pub.close()
        
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
        
    
    def close(self):
        """
        不再执行之后的命令 但当前正在执行的命令还是会后台运行
        """
        try:
            #self.ftp_client.close()
            self.ssh_client.close()
        except:
            pass
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
            t2=Thread(target=self.__heart_beat)
            t3=Thread(target=self.__close_conn)
            
            for t in [t1,t2,t3]:
                t.start()    
    
