# -*- coding: utf-8 -*-

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

from lib.wrapper import gen_background_log_set,connection_error_rerun,command_fliter,logger,logger_err
from lib.utils import my_md5,get_host_ip,cmd_split,is_file_in_dir,safe_decode

from conf import config


#class RemoteHost(MySSH, AbstractHost):  #左边的优先
#class SaltConn(AbstractConn, AbstractHost)

class AbstractHost(object):
    """
    执行命令的抽象类 所有具体实现都应该继承这个类
    """
    extends_postfixs = "extends"                                      #存放扩展命令对应文件的相对目录
    extends_dir = ["",".sh"]                                          #扩展命令对应文件的可选后缀
    
    def __init__(self,redis_log_client,*args, **kargs):
        """继承类应该初始化以下对象"""
        self.redis_log_client=redis_log_client
        
    ######################################################
    ##需要重载的函数  具体的实现方式不同
    def forever_run(self):
        """提供给上层的入口函数"""
        pass
    
    def copy_file(self,*args,**kwargs):
        """复制文件"""
        raise Exception('.copy_file() must be overridden')
    
    def put_file(self,*args,**kwargs):
        """上传文件"""
        raise Exception('.put_file() must be overridden')
    
    def get_file(self,*args,**kwargs):
        """下载文件"""
        raise Exception('.get_file() must be overridden')
    
    def exe_cmd(self,*args,**kwargs):
        """执行命令"""
        raise Exception('.exe_cmd() must be overridden') 
    #####################################################
        
            
    def single_run(self,cmd,cmd_uuid,ip_tag,extend_pattern="\s*__\w+__($|\s)"):
        """
        单个命令的执行
        
        """
        #logger.debug("----------------------------------")

        exe_result={}

        begin_timestamp=time.time()
        exe_result["begin_timestamp"]=begin_timestamp
        exe_result["cmd"]=cmd
        exe_result["uuid"]=cmd_uuid
        exe_result["exe_host"]=ip_tag
        exe_result["from_host"]=get_host_ip()
        
        logger.debug(str(exe_result)+" begin")
        
        try:
            stdout, stderr, exit_code = command_fliter(cmd, config.deny_commands)
            if (stdout, stderr, exit_code) == (None,None,None): 
                #扩展命令以 "__"包围前后 使用格式如下
                #cmd="__xxx__ ..."
                #cmd=" __xxx__ ..."
                if extend_pattern and re.match(extend_pattern,cmd):
                    exe_result,stdout,stderr,exit_code=self.__exe_extend(cmd, exe_result, ip_tag)
    
                else:
                    cmd_type="CMD"
                    exe_result["cmd_type"]=cmd_type
                    self.set_log(ip_tag,exe_result,is_update=False)      #命令执行前                   
    
                    stdout, stderr, exit_code=self.exe_cmd(cmd,background_log_set=gen_background_log_set(cmd_uuid,self.redis_log_client),ip_tag=ip_tag)
        except:
            logger_err.error(format_exc())
            stdout, stderr, exit_code="","some error happen when execute,please check the log",1

        exe_result["stdout"]=stdout
        exe_result["stderr"]=stderr
        exe_result["exit_code"]=exit_code   

        exe_result["end_timestamp"]=time.time()

        self.set_log(ip_tag,exe_result)               #命令执行完毕后更新日志

        logger.debug(str(exe_result)+" done")
        #logger.debug("----------------------------------")           
           
           
    def gen_set_step(self,cmd_uuid,name="step"):
        """
        生成设置步骤记录的函数
        如操作中可能有多个步骤，可以任意记录
        """
        def set_step(step="",name=name):
            self.redis_log_client.hset(cmd_uuid,name,step)
        return set_step
    
    
    def gen_set_info(self,cmd_uuid):
        """生成用于上传时设置日志的函数"""
        def set_info(current_size,total_size):
            """
            上传下载的回调函数 只能同时存在一个上传或下载操作 否则回调调用出错
            """
            self.redis_log_client.hset(cmd_uuid,"current_size",current_size)
            self.redis_log_client.hset(cmd_uuid,"total_size",total_size)
        return set_info


    def __exe_extend(self, cmd_line, exe_result, ip_tag):
        """
        执行自定义的扩展命令
        格式类似于shell命令即 
        cmd arg1 arg2 ...
        """
        exe_result["cmd_type"]="EXTEND"               
        self.set_log(ip_tag,exe_result,is_update=False)  
        
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
            
            local_md5,remote_md5,is_success,msg=self.send_file(local_file,remote_path,self.gen_set_info(cmd_uuid),self.gen_set_step(cmd_uuid), ip_tag=ip_tag)
            
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
            
            local_md5,remote_md5,is_success,msg=self.get_file(local_path,remote_file,self.gen_set_info(cmd_uuid),self.gen_set_step(cmd_uuid), ip_tag=ip_tag)
        
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
            #扩展目录中的扩展命令
            filename,__cmd=is_file_in_dir(cmd,self.extends_postfixs,os.path.join(config.base_dir,self.extends_dir))
            __cmd=safe_decode(__cmd)
            if __cmd:
                full_cmd="%s(){ %s }; %s %s" % (cmd, __cmd, cmd, " ".join(args))
                stdout,stderr,exit_code = self.exe_cmd(full_cmd,ip_tag=ip_tag)
            else:
                #未实现的命令
                stdout=""
                stderr="extend command [%s]  not define" % cmd
                exit_code="127"               
        
        return exe_result,stdout,stderr,exit_code           
            

    def send_file(self,local_file,remote_path,set_info,set_step,ip_tag):
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
        if self.redis_log_client.hexists(config.prefix_put+ip_tag,local_md5):
            #已经存在其他上传操作的情况
            wait_flag = 1 
        else:
            wait_flag = 0
        
        #可以在等待过程中删除标记结束等待
        while wait_flag and self.redis_log_client.hexists(config.prefix_put+ip_tag,local_md5):
            exist_remote_file = self.redis_log_client.hget(config.prefix_put+ip_tag,local_md5)
            if exist_remote_file:
                #远端已经存在文件
                wait_flag = 0
                try:
                    set_step("copying","remote_md5")
                    #校验MD5并复制文件
                    remote_md5,local_md5,is_success,error_msg=self.copy_file(exist_remote_file,remote_file,local_md5,\
                                                                            local_filesize,config.is_copy_by_link,set_info,set_step,ip_tag)
                                                                                                                          
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
            self.redis_log_client.hset(config.prefix_put+ip_tag,local_md5,"")
            try:
                local_md5,remote_md5,is_success,error_msg=self.put_file(local_md5,local_file,remote_path,set_info,set_step,ip_tag)
                
                #redis断开即导致上传失败 无需确保日志回写
                if is_success:
                    self.redis_log_client.hset(config.prefix_put+ip_tag,local_md5,remote_file)
                else:
                    self.redis_log_client.hdel(config.prefix_put+ip_tag,local_md5)
                    
                return local_md5,remote_md5,is_success,error_msg
            except:
                self.redis_log_client.hdel(config.prefix_put+ip_tag,local_md5)
                logger_err.error(format_exc())
                return "","",0,"upload failed"
        else:
            return "","",0,"some thing error in upload"


    #确保当前执行的命令日志正确返回
    @connection_error_rerun()
    def set_log(self,ip_tag,exe_result,is_update=True):
        """
        设置日志
        """
        log_uuid=exe_result["uuid"]
        if is_update:
            self.redis_log_client.expire(log_uuid,config.cmd_log_expire_sec)      #获取返回值后设置日志过期时间
        else:
            self.redis_log_client.rpush(config.prefix_log_host+ip_tag,log_uuid)
        self.redis_log_client.hmset(log_uuid,exe_result)




        