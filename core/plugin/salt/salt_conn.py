# -*- coding: utf-8 -*-
import os
import re
import time
import salt.client
from traceback import format_exc

from lib.utils import Singleton,get_host_ip,my_md5,cmd_split
from lib.mysalt import MySalt
from lib.wrapper import logger,logger_err
from lib.redis_conn import RedisConn

from core.abstract import abstract_conn 
from core.abstract.abstract_conn import AbstractConn
from core.abstract.abstract_host import AbstractHost

from conf import config

#全部使用自己的连接池
_redis_connect=RedisConn()          

def check_host_conn(host_info, redis_config_list, *args, **kargs):
    """
    创建连接进行的操作
    由于使用分布式架构连接一直存在 因而在此为检查连接状态的操作
    ip别名心跳不维护 存在ip别名时每次连接重新判断
    """
    s=MySalt()
    ip=host_info["ip"]
    tag=host_info.get("tag") or ip
    r=s.ping(ip)    
    if ip not in r or not r[ip]:
        raise Exception("%s lost" % ip)
    
    #存在连接则设置心跳  不能一直保持 防止有主机退出salt
    redis_send_client=_redis_connect.refresh(redis_config_list[0])    
    redis_send_client.set(config.prefix_heart_beat+tag,time.time())
    redis_send_client.expire(config.prefix_heart_beat+tag,config.host_check_success_time)


abstract_conn.check_host_conn=check_host_conn

#只是单进程实现单例 
#多进程每个进程都创建一个 都是竞争从队列获取命令 符合预期设置
@abstract_conn.preinit
@Singleton
class SaltConn(AbstractConn, AbstractHost):
    """
    使用salt分发命令
    """    
    
    def __init__(self,host_info,redis_config_list,redis_connect=None,*args,**kwargs):
        self.salt=MySalt(c_path=u"/etc/salt/master")
        self.init(redis_config_list,_redis_connect)
        #使用装饰器不能通过super调用
        #super(SaltConn, self).__init__
    
    
    #重载AbstractHost的函数
    def copy_file(self,exist_remote_file,remote_file,local_md5,local_filesize=None,is_copy_by_link=True,set_info=None,set_step=None,ip_tag=None):
        ip=ip_tag.split("_")[0]
        r=self.salt.link(ip,exist_remote_file,remote_file)
        remote_md5=local_md5
        msg=""
        #返回值有可能是字符串
        if not (r[ip]==True):
            msg=str(r)
            
        return remote_md5,local_md5,remote_md5==local_md5,msg
        
        
    #重载AbstractHost的函数
    def put_file(self,local_md5,local_file,remote_path,set_info=None,set_step=None,ip_tag=None):
        ip=ip_tag.split("_")[0]
        r=self.salt.put(ip,local_file,remote_path,local_md5)
        remote_md5=local_md5
        msg=""
        if not r["is_success"]:
            remote_md5=""
            msg="put file failed"
        
        return local_md5,remote_md5,local_md5==remote_md5,msg
        
    
    #重载AbstractHost的函数
    def get_file(self,local_path,remote_file,set_info,set_step=None,ip_tag=None):
        ip=ip_tag.split("_")[0]
        r=self.salt.get(ip,local_path,remote_file) 
        local_md5=""
        remote_md5=""
        msg=""
        if not r[ip]:
            local_md5="get file failed"
            if not self.salt.local.opts['file_recv']:
                msg="[file_recv=True] must set on salt master's config file"
            elif os.path.isfile(local_path):                        
                msg="local path is a file"
            elif not self.salt.file_exists(ip,remote_file)[ip]:
                msg="remote file not exist"
            else:
                msg="some error happen when get file from remote host"  
        
        return local_md5,remote_md5,local_md5==remote_md5,msg

    
    #动态重载AbstractHost的函数
    def exe_cmd(self,cmd,background_log_set=None,ip_tag=None):
        ip=ip_tag.split("_")[0]
        r=self.salt.exe(ip,cmd)[ip]
        stdout,stderr,exit_code,pid=(r["stdout"],r["stderr"],r["retcode"],r["pid"])
        return stdout,stderr,exit_code
        
    
    #重载AbstractConn的函数
    def single_exe(self,cmd,cmd_uuid,ip_tag):        
        self.single_run(cmd,cmd_uuid, ip_tag)
    
    
    #重载AbstractConn的函数    
    def conn_manage(self):
        """ 
        单次连接状态管理
        用于刷新heart_beat
        ip别名心跳不维护 存在ip别名时每次连接重新判断
        """
        
        r=self.salt.ping("*")
        for ip in r.keys():
            if r[ip]:
                #salt-minion可以正常连接的情况
                self.redis_send_client.set(config.prefix_heart_beat+ip,time.time())
                self.redis_send_client.expire(config.prefix_heart_beat+ip,config.host_check_success_time)
                logger.debug("%s heart beat" % ip)
            
