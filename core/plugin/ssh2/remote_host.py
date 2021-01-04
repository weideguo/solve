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
from lib.utils import Singleton,get_host_ip,my_md5,cmd_split

from core.abstract import abstract_conn 
from core.abstract.abstract_conn import AbstractConn
from core.abstract.abstract_host import AbstractHost
from core.abstract.parallel import AbstractThread

from conf import config


password=Password(aes_key=config.aes_key)

#全部使用自己的连接池
_redis_connect=RedisConn()        
redis_config_client=_redis_connect.refresh(config.redis_config)


def init_ssh(host_info):
    host_info["passwd"] = password.decrypt(str(host_info.get("passwd","")))
    myssh=MySSH(host_info)
    myssh.init_conn()
    return myssh
    

def _copy_file(exist_remote_file,remote_file,local_md5,local_filesize=None,is_copy_by_link=True,set_info=None,set_step=None,ip_tag=None):
    host_info=redis_config_client.hgetall(config.prefix_realhost+ip_tag)
    myssh=init_ssh(host_info)
    r=myssh.copy_file(exist_remote_file,remote_file,local_md5,local_filesize,is_copy_by_link,set_info,set_step,ip_tag)
    myssh.close()
    return r    
    
    
def _put_file(local_md5,local_file,remote_path,set_info=None,set_step=None,ip_tag=None):
    host_info=redis_config_client.hgetall(config.prefix_realhost+ip_tag)
    myssh=init_ssh(host_info)
    r=myssh.put_file(local_md5,local_file,remote_path,set_info,set_step,ip_tag)
    myssh.close()
    return r
    

def _get_file(local_path,remote_file,set_info,set_step=None,ip_tag=None):
    host_info=redis_config_client.hgetall(config.prefix_realhost+ip_tag)
    myssh=init_ssh(host_info)
    r=myssh.get_file(local_path,remote_file,set_info,set_step,ip_tag)
    myssh.close()
    return r


def _exe_cmd(cmd,background_log_set=None,ip_tag=None):
    host_info=redis_config_client.hgetall(config.prefix_realhost+ip_tag)
    myssh=init_ssh(host_info)
    r=myssh.exe_cmd(cmd,background_log_set,ip_tag)
    myssh.close()
    return r
    


def check_host_conn(host_info, redis_config_list, *args, **kargs):
    """
    检查是否可连接  
    """
    ip=host_info["ip"]
    tag=host_info.get("tag") or ip
    
    #是否需要这一步？每次主机切换都会运行
    out,err,exit_code=_exe_cmd(cmd="echo 1",background_log_set=None,ip_tag=tag) 
    if exit_code!=0:
        logger_err.debug("stdout,stderr: %s %s" % (out,err) )
        raise Exception("%s lost" % ip)
    
    #存在连接则设置心跳  不一直保持
    redis_send_client=_redis_connect.refresh(redis_config_list[0])    
    redis_send_client.set(config.prefix_heart_beat+tag,time.time())
    redis_send_client.expire(config.prefix_heart_beat+tag,config.host_check_success_time)


abstract_conn.check_host_conn=check_host_conn

#只是单进程实现单例 
#多进程每个进程都创建一个 都是竞争从队列获取命令 符合预期设置
@abstract_conn.preinit
@Singleton
class RemoteHost(AbstractConn, AbstractHost):
    """
    每条命令创建SSH连接、执行、关闭SSH连接模式
    """    
    def __init__(self,host_info,redis_config_list,redis_connect=None,*args,**kwargs):

        self.init(redis_config_list,_redis_connect)    
    
    
    #重载AbstractHost的函数
    def copy_file(self,*args,**kwargs):
        return _copy_file(*args,**kwargs) 
        
        
    #重载AbstractHost的函数
    def put_file(self,*args,**kwargs):
        return _put_file(*args,**kwargs)
        
    
    #重载AbstractHost的函数
    def get_file(self,*args,**kwargs):
        return _get_file(*args,**kwargs)
        

    #动态重载AbstractHost的函数
    def exe_cmd(self,*args,**kwargs):
        
        return _exe_cmd(*args,**kwargs)
        
    
    #重载AbstractConn的函数
    def single_exe(self,*args,**kwargs):        
        self.single_run(*args,**kwargs)
    
    
    #不维护心跳


