# -*- coding: utf-8 -*-
import os
import re
import time
import uuid
import salt.client
from traceback import format_exc

from conf import config
from lib.utils import Singleton,get_host_ip,my_md5,cmd_split
from lib.mysalt import MySalt
from lib.wrapper import logger,logger_err
from ..abstract import abstract_conn
from ..abstract.abstract_conn import AbstractConn

def check_host_conn(host_info):
    """
    创建连接进行的操作
    由于使用分布式架构连接一直存在 因而在此为检查连接状态的操作
    """
    #print("will do something "+str(host_info))
    s=MySalt()
    ip=host_info["ip"]
    r=s.ping(ip)    
    if not r[ip]:
        raise Exception("%s lost" % ip)


abstract_conn.check_host_conn=check_host_conn

@abstract_conn.preinit
@Singleton
class SaltConn(AbstractConn):
    """
    使用salt分发命令
    """    

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

     
    def __send_file(self,ip,local_file,remote_path,salt_conn,cmd_uuid):
        
        if not os.path.isfile(local_file):
            return ("","local file not exist",1)

        file_name=os.path.basename(local_file)
        remote_file=os.path.join(remote_path,file_name)
        local_md5=my_md5(file=local_file)
        put_flag = False
        if self.redis_log_client.hexists(config.prefix_put+ip,local_md5):
            #已经存在其他上传操作的情况
            wait_flag = 1
            while wait_flag:
                exist_remote_file = self.redis_log_client.hget(config.prefix_put+ip,local_md5)
                if exist_remote_file:
                    wait_flag = 0
                    if salt_conn.file_exists(ip,exist_remote_file)[ip]:
                        if exist_remote_file == remote_file:
                            #redis记录存在的文件跟现在的文件一致
                            logger.debug("PUT file exist,will not PUT again")
                            put_flag = False
                        else:
                            #redis记录存在的文件md5跟现在的一致    
                            r=salt_conn.link(ip,exist_remote_file,remote_file)
                            
                            #返回值有可能是字符串
                            if not (r[ip]==True):
                                logger_err.error("create link failed: %s %s" % (exist_remote_file,remote_file))
                                logger_err.error(str(r))
                                put_flag = True    
                            else:
                                logger.debug("ceate link success: %s %s" % (exist_remote_file,remote_file))
                                put_flag = False
                    else:
                        logger.debug("remote file not really exist,will upload: %s" % exist_remote_file)
                        put_flag = True

                else:
                    #如果其他上传还在进行 则等待后再检查
                    self.redis_log_client.hset(cmd_uuid,"remote_md5","waiting others complete:"+str(wait_flag))
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
            self.redis_log_client.hset(config.prefix_put+ip,local_md5,"")
            r=salt_conn.put(ip,local_file,remote_path,local_md5)
            if r["is_success"]:
                self.redis_log_client.hset(config.prefix_put+ip,local_md5,remote_file)
                return (r[ip],"",0)
            else:
                self.redis_log_client.hdel(config.prefix_put+ip,local_md5)
                return ("",r[ip],1)
        else:
            return ("","",0)
 
     
    def single_exe(self,ip,allcmd):
        """
        单次命令的执行 
        可以为阻塞式实行，即可以等执行完毕并获取到结果
        """
        #print("execute by salt %s %s" % (ip,allcmd))
        allcmd=allcmd.split(config.spliter)
        cmd=allcmd[0]
        try:
            cmd_uuid=allcmd[1]
        except IndexError:
            cmd_uuid=uuid.uuid1().hex 
        
        exe_result={}
        exe_result["begin_timestamp"]=time.time()
        exe_result["cmd"]=cmd
        exe_result["uuid"]=cmd_uuid
        exe_result["exe_host"]=ip
        exe_result["from_host"]=get_host_ip(ip)
         
        logger.debug(str(exe_result)+" begin")
        
        try:
            s=MySalt()
             
            #if re.match("PUT:.+?:.+?",cmd) or re.match("GET:.+?:.+?",cmd):
            #    cmd_type=cmd.split(":")[0]
            #    exe_result["cmd_type"]=cmd_type
            #    self.set_log(exe_result,is_update=False)      #命令执行前
            #
            #    if cmd_type=="PUT":
            #        file_flag,local_file,remote_path=cmd.split(":")
            #         
            #        stdout,stderr,exit_code=self.__send_file(ip,local_file,remote_path,s,cmd_uuid)                 
            #
            #    elif cmd_type=="GET":
            #        file_flag,local_path,remote_file=cmd.split(":")
            #        r=s.get(ip,local_path,remote_file) 
            #        if r[ip]:
            #            stdout,stderr,exit_code=("","",0)
            #        else:
            #            stdout=""
            #            exit_code=1
            #            if not s.local.opts['file_recv']:
            #                stderr="[file_recv=True] must set on salt master's config file"
            #            elif os.path.isfile(local_path):                        
            #                stderr="local path is a file"
            #            elif not s.file_exists(ip,remote_file)[ip]:
            #                stderr="remote file not exist"
            #            else:
            #                stderr="some error happen when get file from remote host"
                            
            if re.match("\s*__\w+__($|\s)",cmd):
                exe_result,stdout,stderr,exit_code=self.__exe_extend(cmd, exe_result, s)
            else:
                exe_result["cmd_type"]="CMD"
                self.set_log(exe_result,is_update=False)      #命令执行前  

                r=s.exe(ip,cmd)[ip]
                
                stdout,stderr,exit_code,pid=(r["stdout"],r["stderr"],r["retcode"],r["pid"])
                exe_result["pid"]=pid
        except:
            logger_err.error(format_exc())
            stdout,stderr,exit_code="","some error happen when execute,please check the log",1

        exe_result["stdout"]=stdout
        exe_result["stderr"]=stderr
        exe_result["exit_code"]=exit_code    
        exe_result["end_timestamp"]=time.time()
        self.set_log(exe_result)               #命令执行完毕后更新日志
        logger.debug(str(exe_result)+" done")

    
    def __exe_extend((self, cmd_line, exe_result, s):
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
        
        if cmd_type=="__put__":
            local_file,remote_path=args[0],args[1]
             
            stdout,stderr,exit_code=self.__send_file(ip,local_file,remote_path,s,cmd_uuid)                 
        
        elif cmd_type=="__get__":
            remote_file,local_path=args[0],args[1]
            r=s.get(ip,local_path,remote_file) 
            if r[ip]:
                stdout,stderr,exit_code=("","",0)
            else:
                stdout=""
                exit_code=1
                if not s.local.opts['file_recv']:
                    stderr="[file_recv=True] must set on salt master's config file"
                elif os.path.isfile(local_path):                        
                    stderr="local path is a file"
                elif not s.file_exists(ip,remote_file)[ip]:
                    stderr="remote file not exist"
                else:
                    stderr="some error happen when get file from remote host"  
        return exe_result,stdout,stderr,exit_code
        
        
    def conn_manage(self):
        """ 
        单次连接状态管理
        用于刷新heart_beat
        """
        
        s=MySalt()
        r=s.ping("*")
        for ip in r.keys():
            if r[ip]:
                #salt-minion可以正常连接的情况
                self.redis_send_client.set(config.prefix_heart_beat+ip,time.time())
                self.redis_send_client.expire(config.prefix_heart_beat+ip,config.host_check_success_time)
                logger.debug("%s heart beat" % ip)
            
