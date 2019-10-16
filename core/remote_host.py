#coding:utf8

import uuid
import os
import re
import random
import time
import sys
if sys.version_info>(3,0):
    import queue as Queue
else:
    import Queue
from threading import Thread
from traceback import format_exc

import redis
import paramiko
from paramiko import SSHClient

from lib.logger import logger,logger_err
from lib.utils import my_md5,get_host_ip
from conf import config


class RemoteHost():
    """
    SSH远程连接类
    在远端执行命令 上传下载文件
    持续监听队列获取命令
    续监听队列判断是否关闭连接
    """
    
    def __init__(self,host_info,redis_send_pool,redis_log_pool,t_number=config.max_concurrent_thread):
        self.host_info=host_info
        self.redis_send_pool=redis_send_pool
        self.redis_log_pool=redis_log_pool

        self.ssh_client=None
        #self.ftp_client=None
        self.redis_send_client=None
        self.redis_log_client=None

        self.thread_q=Queue.Queue(t_number)   #单个主机的并发
        self.t_thread_q=Queue.Queue(t_number) #用于存储正在运行的队列 
        self.is_run=False                      #后台运行         

       
    def init_conn(self):
        """
        初始化连接
        """
        self.redis_send_client=redis.StrictRedis(connection_pool=self.redis_send_pool)
        self.redis_log_client=redis.StrictRedis(connection_pool=self.redis_log_pool)

        #self.redis_send_client.set("initing_"+self.host_info["ip"],time.time())
        client = SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        host_info=self.host_info

        client.connect(hostname=host_info["ip"],port=int(host_info["ssh_port"]), username=host_info["user"],\
                        password=host_info["passwd"])

        self.ssh_client=client
        #self.ftp_client=client.open_sftp()
        self.is_run=True
        #self.redis_send_client.expire("initing_"+self.host_info["ip"],60*60)


    def exe_cmd(self,cmd):
        """
        执行命令
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd)

        out=stdout.read()
        err=stderr.read()
        exit_code=stdout.channel.recv_exit_status()
        return out,err,exit_code

    def md5_remote(self,ftp_client,fullname):
        """
        计算远端的MD5
        """
        md5 = ""
        try:
            # 在远端计算MD5值，不必将文件读取到本地再计算，但有可能出现错误
            md5_raw,err,exit_code =self.exe_cmd("md5sum "+fullname)
            md5=md5_raw.split(" ")[0]
            #logger_err.debug("calculate in remote: %s %s %s" %(md5,err,exit_code))
        except:
            exit_code=-100        
    
        if exit_code != 0:
            md5 = my_md5(afile=ftp_client.open(fullname))
            #logger_err.debug("calculate in local: %s" %(md5))

        return md5
        
    def send_file(self,local_file,remote_path,c_uuid):
        """
        从本地上传文件到远端 文件名不变
        远端目录如果不存在 则创建一个
        远端文件如果存在 则使用时间戳重命名远端文件
        """
        def set_send_info(current_size,total_size):
            self.redis_log_client.hset(c_uuid,"current_size",current_size)
            self.redis_log_client.hset(c_uuid,"total_size",total_size)

        ftp_client=self.ssh_client.open_sftp()

        file_name=os.path.basename(local_file)
        remote_file=os.path.join(remote_path,file_name)

        local_md5=my_md5(file=local_file)
        local_filesize=os.path.getsize(local_file)
        
        put_flag = False
        if self.redis_log_client.hexists(config.prefix_put+self.host_info["ip"],local_md5):
            #已经存在其他上传操作的情况
            wait_flag = 1 
            while wait_flag:
                exist_remote_file = self.redis_log_client.hget(config.prefix_put+self.host_info["ip"],local_md5)
                if exist_remote_file:
                    wait_flag = 0
                    if self.is_remote_file(ftp_client,exist_remote_file):
                        #复制已经存在的文件
                        try:
                            self.redis_log_client.hset(c_uuid,"remote_md5","copying")
                            should_upload=self.remote_mkdirs(ftp_client,remote_file,local_md5)
                            if should_upload:
                                if config.is_copy_by_link:
                                    ftp_client.symlink(exist_remote_file,remote_file)
                                else:
                                    ftp_client.putfo(ftp_client.open(exist_remote_file),remote_file,local_filesize,callback=set_send_info)
                            
                        except:
                            logger_err.error(format_exc())
                            return "","",0,"copy remote file failed"
                    else:
                        #如果远端文件不存在 则需要再次上传
                        put_flag = True
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
            self.redis_log_client.hset(config.prefix_put+self.host_info["ip"],local_md5,"")
            try:
                should_upload=self.remote_mkdirs(ftp_client,remote_file,local_md5)
            except:
                self.redis_log_client.hdel(config.prefix_put+self.host_info["ip"],local_md5)
                logger_err.error(format_exc())
                return "","",0,"create remote dir failed"            

            if should_upload:
                try:
                    ftp_client.put(local_file,remote_file,callback=set_send_info)                 #使用回调函数设置传输进度
                    self.redis_log_client.hset(config.prefix_put+self.host_info["ip"],local_md5,remote_file)
                except:
                    self.redis_log_client.hdel(config.prefix_put+self.host_info["ip"],local_md5)
                    logger_err.error(format_exc())
                    return "","",0,"upload failed"

        if config.is_copy_by_link:
            remote_md5=local_md5
        else:
            #remote_md5=my_md5(afile=ftp_client.open(remote_file))
            remote_md5=self.md5_remote(ftp_client,remote_file)

        is_success = (local_md5==remote_md5)
        
        ftp_client.close()

        return local_md5,remote_md5,is_success,""
            

    def get_file(self,local_path,remote_file,c_uuid):
        """
        下载文件到本地 文件名不变
        如果本地文件存在 则使用时间戳重命名现有文件
        如果本地目录不存在 则创建
        """
        ftp_client=self.ssh_client.open_sftp()

        file_name=os.path.basename(remote_file)
        local_file=os.path.join(local_path,file_name)

        if os.path.exists(local_file):
            os.rename(local_file,local_file+"_"+str(time.time()))
        elif not os.path.exists(local_path):
            try:
                os.makedirs(local_path)
            except:
                return "","",0,"create local dir failed"
        elif os.path.isfile(local_path):
            return "","",0,"create local dir failed,it is a file"

        def set_get_info(current_size,total_size):
            self.redis_log_client.hset(c_uuid,"current_size",current_size)
            self.redis_log_client.hset(c_uuid,"total_size",total_size) 
        
        ftp_client.get(remote_file,local_file,set_get_info)

        local_md5=my_md5(file=local_file)
        #remote_md5=my_md5(afile=ftp_client.open(remote_file))
        remote_md5=self.md5_remote(ftp_client,remote_file)
        is_success = (local_md5==remote_md5)
    
        ftp_client.close()
        return local_md5,remote_md5,is_success,""


    def is_remote_file(self,ftp_client,remote_file):
        """
        判断远端文件是否存在
        """
        try:
            #给的路径可能为目录
            ftp_client.listdir(remote_file)                #
            return False
        except:
            remote_dir,remote_filename=os.path.split(remote_file)
            try:
                if remote_filename in ftp_client.listdir(remote_dir):        
                    return True
                else:
                    return False
            except:
                return False

    def remote_mkdirs(self,ftp_client,remote_file,local_md5):
        """
        由远端文件完整路径在远端创建目录 并有MD5确定是否要再次上传
        """
        should_upload=True
        remote_file_list=[]
        try:
            remote_path = os.path.dirname(remote_file)
            remote_file_list=ftp_client.listdir(remote_path)
        except:
            remote_file_list=[]

        file_name = os.path.basename(remote_file)
        if file_name in remote_file_list:
            #远端文件存在 重命名
            logger_err.debug("local_md5: %s" % local_md5)
            try:
                remote_md5 = self.md5_remote(ftp_client,remote_file)
            except:
                #由于文件可能是软连接 而原来的文件在已经被删除的情况下读取失败                
                remote_md5=""

            if local_md5 == remote_md5:
                should_upload=False
            else:
                try:
                    ftp_client.posix_rename(remote_file,remote_file+"_"+str(time.time()))
                except:
                    ftp_client.rename(remote_file,remote_file+"_"+str(time.time()))
        else:
            #远端文件夹如果不存在则创建  类似 mkdir -p
            p=os.path.dirname(remote_file)
            dir_list=[]
            while True:
                try:
                    ftp_client.listdir(p)
                    break
                except:
                    dir_list.append(p)
                    p=os.path.dirname(p)

            dir_list.reverse()

            for d in dir_list:
                ftp_client.mkdir(d)

        return should_upload

      
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
        exe_result["exe_host"]=self.host_info["ip"]
        exe_result["from_host"]=get_host_ip(self.host_info["ip"])

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
                    
                    if os.path.isfile(local_file):
                        local_md5,remote_md5,is_success,err_msg=self.send_file(local_file,remote_path,exe_result["uuid"])
                    else:
                        local_md5,remote_md5,is_success,err_msg=("","",0,"local file not exist")

                elif cmd_type=="GET":
                    file_flag,local_path,remote_file=cmd.split(":") 
                    remote_file=remote_file.rstrip()
                    
                    if self.is_remote_file(ftp_client,remote_file):
                        local_md5,remote_md5,is_success,err_msg=self.get_file(local_path,remote_file,exe_result["uuid"])
                    else:
                        local_md5,remote_md5,is_success,err_msg=("","",0,"remote file not exist")

                exe_result["local_md5"]=local_md5
                exe_result["remote_md5"]=remote_md5
                exe_result["is_success"]=int(is_success)
                
                stdout=""
                stderr=err_msg
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
            self.redis_log_client.rpush(config.prefix_log_host+self.host_info["ip"],log_uuid)
        self.redis_log_client.hmset(log_uuid,exe_result)

   
    def __forever_run(self):
        """
        持续监听由redis队列获取命令
        通过线程开启并发操作 
        """

        key=config.prefix_cmd+self.host_info["ip"]
        cmd_spliter=config.cmd_spilter

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
                    allcmd=allcmd.split(cmd_spliter)        
                    cmd=allcmd[0]
                    try:
                        cmd_uuid=allcmd[1]
                    except IndexError:
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
            logger.debug("%s heart beat" % self.host_info["ip"])
            self.redis_send_client.set(config.prefix_heart_beat+self.host_info["ip"],time.time())
            time.sleep(config.heart_beat_interval)

        self.redis_send_client.delete(config.prefix_heart_beat+self.host_info["ip"])
        

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
            kill_ip=kill_info[-1]

            if kill_ip==self.host_info["ip"]:            
                self.is_run=False
                self.redis_send_client.set(config.prefix_closing+self.host_info["ip"],time.time())    #标记host处于关闭状态，不再执行新命令
                #正在运行的并发运行完毕后再退出
                while not self.t_thread_q.empty():
                    t=self.t_thread_q.get()
                    t.join()

                self.close()
                break

        self.redis_send_client.delete(config.prefix_heart_beat+self.host_info["ip"])
        self.redis_send_client.expire(config.prefix_closing+self.host_info["ip"],config.closing_host_flag_expire_sec)      #关闭已经完成  
    

    def close(self):
        """
        不再执行之后的命令 但当前正在执行的命令还是会后台运行
        """
        #self.ftp_client.close()
        self.ssh_client.close()
        self.is_run=False
        #self.redis_send_client=None            #不重置以确保redis还能用于重置命令队列 
        #self.redis_log_client=None        

        logger.info("%s is closed" % self.host_info["ip"])



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

        
