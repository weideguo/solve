# -*- coding: utf-8 -*-
import os
import re
import uuid
import time
import platform 
from threading import Thread
from traceback import format_exc

from jinja2 import Template

from lib.utils import safe_decode
from lib.wrapper import logger,logger_err
from lib.redis_conn import RedisConn
from conf import config

class ClusterExecution(object):
    """
    cluster（执行对象）的执行类
    逐行读取playbook，使用自己的配置参数进行替换，然后运行
    远端主机的连接的创建在此具体控制
    """
    
    def __init__(self,cluster_id,redis_config_list,redis_connect=None):
        """
        每一次执行创建一个对象，运行完毕后销毁
        对多个集群执行时，创建多个对象
        多个集群多次需要创建多个对象

        """
        if redis_connect:
            self.redis_connect=redis_connect
            self.is_disconnect=False
        else:
            self.redis_connect=RedisConn(config.cluster_redis_pool_size)
            self.is_disconnect=True
        
        self.redis_send_config=redis_config_list[0]
        self.redis_log_config=redis_config_list[1]
        self.redis_tmp_config=redis_config_list[2]
        self.redis_job_config=redis_config_list[3]       
        self.redis_config_config=redis_config_list[4]
        
        self.redis_config_list=redis_config_list
        
        self.redis_refresh()
        
        self.exe_next=True
        
        self.cluster_id=cluster_id         #全局uuid 用于标记cluster的日志 global变量的存储
        self.target=""
        self.current_host="" 
        self.current_uuid=""               #当前命令的uuid
        self.exe_uuid_list=[]              #正在运行的命令的uuid列表 如果依赖前项则逐个uuid检测获取结果再判断是否执行下一步 
        
        if not self.cluster_id:
            self.cluster_id=uuid.uuid1().hex
        
        self.global_key=config.prefix_global+config.spliter+self.cluster_id
        self.select_key=config.prefix_select+config.spliter+self.cluster_id
        self.kill_key=config.prefix_kill+cluster_id
        
        self.block_key=config.prefix_block+cluster_id
        
        
        self.sum_key=config.prefix_sum+self.cluster_id 
        self.log_target=config.prefix_log_target+self.cluster_id
        
        
    def redis_refresh(self):
        self.redis_send_client=self.redis_connect.refresh(self.redis_send_config)
        self.redis_log_client=self.redis_connect.refresh(self.redis_log_config) 
        self.redis_tmp_client=self.redis_connect.refresh(self.redis_tmp_config)
        self.redis_job_client=self.redis_connect.refresh(self.redis_job_config)        
        self.redis_config_client=self.redis_connect.refresh(self.redis_config_config)      
        
        self.redis_client_list=[self.redis_send_client,self.redis_log_client,self.redis_tmp_client,self.redis_job_client,self.redis_config_client]
       
    
    def get_value(self,target_name,name_str):
        """
        如 db1.host.ip 获取参数值
        """
        name_str=name_str.strip()
        key_name=target_name
        pattern='^(%s|%s|%s)\s*\..*' % (config.prefix_global,config.prefix_session,config.prefix_select)
        
        if re.match(pattern,name_str):
            change=False
        else:
            change=True
        i=0
        for n in name_str.split("."):
            n=n.strip()
            if i and change:
                key_name=self.redis_config_client.hgetall(key_name)[n]
            else:
                key_name=self.redis_tmp_client.hgetall(key_name)[n]
                i = i+1

        return key_name


    def reset(self):
        """
        重置
        """
        self.current_host=""
        self.exe_next=True
        self.exe_uuid_list=[] 
        self.current_uuid=""
        self.cluster_id=""
        self.target="" 
        
        if self.is_disconnect:
            for client in self.redis_client_list:
                try:
                    client.connection_pool.disconnect()
                except:
                    pass

    
    def render(self,target,cmd):
        """
        使用jinja2模板方法替换命令中的变量 
        变量存在左右空格不影响，会被清除
        变量中间不能存在空格
        """
        data={}
        for c in re.findall("(?<={{).+?(?=}})",cmd):
            #c_r=c.replace(".","_____")                   #.被jinja2特殊使用 因此使用_____临时替代
            c_r=re.sub("\s*\.\s*","_____",c).strip()      #去除字符串的左右空格 以及.左右的空格
            cmd=cmd.replace(c,c_r)
            data[c_r]=safe_decode(self.get_value(target,c))
              
        real_cmd=Template(cmd).render(data)      
        return real_cmd
        
    
    def run(self,target,playbook,begin_line):
        """
        后台运行
        """
        self.target=target
        t=Thread(target=self.exe,args=(target,playbook,begin_line))
        t.start()


    def exe(self,target,playbook,begin_line=0):
        """
        playbook执行入口 线程不安全 如果多线程需要每次都创建对象
        当执行命令到一半出现redis连接错误，则只执行完当前的命令，之后的命令不会再执行
        """        
        cluster_start_time=time.time()           
        
        logger.info("<%s %s>  %s begin" % (target,self.cluster_id,playbook)) 

        self.redis_tmp_client.hset(target,config.prefix_global,self.global_key)
        self.redis_tmp_client.hset(target,config.prefix_select,self.select_key)
        
        stop_str=""          #用于标记执行结束的信息
        last_uuid=""         #最后分发的命令的uuid 用于判断playbook执行是否正常退出
        
        stop_info={}
        stop_info["begin_timestamp"]=cluster_start_time        
        stop_info["target"]=self.target        
        
        self.redis_log_client.hmset(self.sum_key,stop_info)        
        
        
        #是否暂停
        pause_tag=0
        
        def pause(key, pause_tag):
            """
            用于执行暂停
            
            """
            if not pause_tag:
                if self.redis_send_client.exists(key):
                    #只要存在key一次，则全部进行暂停
                    pause_tag=1
                    #队列第一次的第一个值只用于判断是否暂停，不控制执行，因此先移除
                    self.redis_send_client.blpop(key,1)
                    
            stop_str=""
            if pause_tag:
                self.redis_log_client.hset(self.current_uuid,"stdout","pausing")
                block_tag=self.redis_send_client.blpop(key, timeout=config.tmp_config_expire_sec)
                self.redis_log_client.hdel(self.current_uuid,"stdout")
                if block_tag:
                    
                    try:
                        stop_str = int(block_tag[-1])
                        if stop_str <  0:
                            #插入<0 则不再阻塞 
                            pause_tag=0
                        
                        #插入>0的数 继续下一步
                        stop_str=""    
                    except:
                        #字符说明存在中断
                        stop_str = str(block_tag[-1])
                else:
                    #超时
                    stop_str = "pause timeout"
            else:
                stop_str = ""
        
            return stop_str,pause_tag
        
        
        try:
            with open(playbook,"r") as f:
                
                next_cmd=f.readline()
                current_line=1            
                while next_cmd and self.exe_next:
                    #去除所有命令的左右空格以及换行符，并转换成unicode格式
                    next_cmd=next_cmd.strip()
                    next_cmd=safe_decode(next_cmd)
                    
                    self.current_uuid=uuid.uuid1().hex
                    if current_line < begin_line:
                        #主机切换的命令正常运行
                        if re.match("^\[.*\]$",next_cmd):
                            cmd=next_cmd
                        else:
                            cmd=""
                    else:
                        cmd=next_cmd
                    
                    self.redis_log_client.rpush(self.log_target,self.current_uuid)
                    """
                    每一行命令的日志id都放入日志队列 
                    根据日志队列、playbook即可获知执行到哪一行结束
                    以及每一行的执行结果
                    """
                    
                    if re.match("^#",cmd) or re.match("^$",cmd):
                        #空白以及注释行单独判断
                        stop_str,pause_tag = pause(self.block_key,pause_tag)
                        
                        if stop_str:
                            
                            self.redis_log_client.hset(self.current_uuid,"exit_code",stop_str)
                            self.redis_log_client.hset(self.current_uuid,"stderr",stop_str)
                            self.redis_log_client.hset(self.current_uuid,"stdout","")
                            self.exe_next=False                   
                            self.redis_log_client.expire(self.current_uuid,config.cmd_log_expire_sec)
                            break
                        
                        #结束暂停判断
                    
                        #跳过注释以及空白行
                        logger.debug("origin command: %s ---- <%s %s> will not execute" % (next_cmd,self.target,self.cluster_id))
                        
                    else:
                        self.redis_log_client.hset(self.current_uuid,"start_timestamp",time.time())       
                        self.redis_log_client.hset(self.current_uuid,"origin_cmd",cmd)
                    
                        logger.debug("origin command: %s ------------ <%s %s> %s" % (cmd,self.target,self.cluster_id,self.current_uuid))
                        try:
                            cmd=self.render(target,cmd)
                        except:
                            logger_err.error(format_exc())
                            self.redis_log_client.hset(self.current_uuid,"exit_code","render error")
                            self.redis_log_client.hset(self.current_uuid,"stderr","render error")
                            self.redis_log_client.hset(self.current_uuid,"stdout","")
                            self.exe_next=False                   
                            self.redis_log_client.expire(self.current_uuid,config.cmd_log_expire_sec)
                            break
    
                        cmd=cmd.strip()
                    
                        self.redis_log_client.hset(self.current_uuid,"render_cmd",cmd)
    
                        logger.debug("render command: %s ------------ <%s %s> %s" % (cmd,self.target,self.cluster_id,self.current_uuid))
                        
                        #进行暂停判断 先渲染后暂停
                        stop_str,pause_tag = pause(self.block_key,pause_tag)
                        
                        if stop_str:
                            
                            self.redis_log_client.hset(self.current_uuid,"exit_code",stop_str)
                            self.redis_log_client.hset(self.current_uuid,"stderr",stop_str)
                            self.redis_log_client.hset(self.current_uuid,"stdout","")
                            self.exe_next=False                   
                            self.redis_log_client.expire(self.current_uuid,config.cmd_log_expire_sec)
                            break
                        
                            
                        #结束暂停判断
                    
                        #[ip_addr] 主机切换命令 
                        if re.match("^\[.*\]$",cmd):
                            self.__host_change(cmd,self.current_uuid)                        
                            self.__check_result([self.current_uuid])
                        
                        #没有预先切换主机则终止
                        elif not self.current_host:
                            self.redis_log_client.hset(self.current_uuid,"exit_code","current_host null")
                            self.redis_log_client.hset(self.current_uuid,"stderr","should execute [<ip>] before any command")
                            self.redis_log_client.hset(self.current_uuid,"stdout","")
                            self.exe_next=False
                            self.redis_log_client.expire(self.current_uuid,config.cmd_log_expire_sec)                            
                            break
                        
                        #脚本全局变量设置
                        #elif re.match("^global\..+=",cmd):
                        elif re.match("^"+config.prefix_global+"\..+=",cmd):
                            self.__global_var(cmd,self.current_uuid)
                        
                        #选择变量设置
                        #elif re.match("^select\..+=",cmd):
                        elif re.match("^"+config.prefix_select+"\..+=",cmd):
                            if not self.__select_var(cmd,self.current_uuid):
                                self.exe_next=False
                                stop_str="select failed"
                                break
    
                        #普通命令 简单的shell命令
                        else:
                            self.__single_exe(self.current_host,cmd,self.current_uuid)
                    
                        self.redis_log_client.hset(self.current_uuid,"stop_timestamp",time.time())
    
                    #从redis获取信息，判断是否进行kill操作终止之后的命令
                    if self.redis_send_client.get(self.kill_key):        
                        self.redis_send_client.expire(self.kill_key,config.kill_cluster_expire_sec)
                        self.exe_next=False
                        logger.info("get kill signal in <%s %s>" % (self.target,self.cluster_id))
                        stop_str="killed" 
    
                    
                    self.redis_log_client.expire(self.current_uuid,config.cmd_log_expire_sec)
                    next_cmd=f.readline()    
                    current_line=current_line+1
            
            last_uuid=self.current_uuid
            last_cmd_info=self.redis_log_client.hgetall(last_uuid)
                
            if not stop_str:
                if last_cmd_info:
                    if str(last_cmd_info["exit_code"])=="0" and not last_cmd_info["stderr"]:
                        stop_str="done"
                    else:        
                        stop_str=str(last_cmd_info["exit_code"])
                else:
                    stop_str="done"
        except:
            logger_err.error(format_exc())
            stop_str="unexpected err"
        
        
        stop_info["stop_str"]=stop_str
        stop_info["end_timestamp"]=time.time()
        stop_info["last_uuid"]=last_uuid
        
        last_stdout=self.redis_log_client.hget(last_uuid,"stdout")
        if not last_stdout:
            last_stdout=""
        stop_info["last_stdout"]=last_stdout

        logger.info("%s %s %s" % (self.cluster_id,self.sum_key,stop_info))        

        self.redis_log_client.hmset(self.sum_key,stop_info) 
        
        
        if stop_str=="done":        
            logger.info("<%s %s>  %s  done" % (target,self.cluster_id,playbook))
        else:
            logger.info("<%s %s>  %s  fail" % (target,self.cluster_id,playbook))
 
        self.redis_tmp_client.expire(self.global_key,config.tmp_config_expire_sec)
        self.redis_tmp_client.expire(self.select_key,config.tmp_config_expire_sec)
        self.redis_tmp_client.expire(target,config.tmp_config_expire_sec)
        
        self.reset()


    def __single_exe(self,host,cmd,c_uuid=""):
        """
        将命令放入redis 
        从redis查询结果  
        """

        if not c_uuid:
            c_uuid=uuid.uuid1().hex

        logger.debug("-------------- <%s %s> %s %s %s accept" % (self.target,self.cluster_id,host,cmd,c_uuid))
        
        if re.match("^wait$",cmd.strip()):
            #对wait命令特殊处理
            check_result_block=True
            self.__check_result(self.exe_uuid_list)
            self.redis_log_client.hset(self.current_uuid,"stderr","")
            if self.exe_next==False:
                self.redis_log_client.hset(self.current_uuid,"exit_code",config.wait_exit_code)
            else:
                self.redis_log_client.hset(self.current_uuid,"exit_code",0)    
            #self.redis_log_client.expire(self.current_uuid,config.cmd_log_expire_sec)
            self.exe_uuid_list=[]
            r=""
        elif re.match(".*&$",cmd.strip()):
            #特殊处理如   shell command &   
            #print self.exe_uuid_list
            self.exe_uuid_list.append(c_uuid)
            check_reault_block=False 
            #print c_uuid,self.exe_uuid_list,self.target 
            cmd=re.sub("&\s*?$","",cmd)
            self.redis_send_client.rpush(config.prefix_cmd+host,cmd+config.spliter+c_uuid)
            r=""
        else:        
            self.redis_send_client.rpush(config.prefix_cmd+host,cmd+config.spliter+c_uuid)        
            r=self.__check_result([c_uuid])[0]["stdout"].replace("\n","")   
 
        logger.debug("-------------- <%s %s> %s %s %s complete" % (self.target,self.cluster_id,host,cmd,c_uuid))        

        return r    


    def __host_change(self,cmd,current_uuid):
        """
        将连接信息插入队列 控制主机的连接 并切换当前接受命令的主机        
        """

        self.current_host=cmd.replace("[","").replace("]","").strip()

        if self.current_host:
            #将主机ip放入初始化队列 由其他线程后台初始化连接
            self.redis_send_client.rpush(config.key_conn_control,self.current_host+config.spliter+current_uuid)
            self.redis_log_client.hset(current_uuid,"uuid",current_uuid)

            #阻塞到host启动完毕
            def get_heart_beat():
                heart_beat=self.redis_send_client.get(config.prefix_heart_beat+self.current_host)
                if not heart_beat:
                    heart_beat=0
                return heart_beat

            retry_flag=0
            while time.time()-float(get_heart_beat())>config.host_check_success_time and retry_flag<config.host_check_wait \
                  and self.exe_next and (not self.redis_log_client.hget(current_uuid,"exit_code")):
                time.sleep(config.host_check_time)
                retry_flag = retry_flag+1
                self.redis_log_client.hset(current_uuid,"desc","ckeck:"+str(retry_flag))

            if retry_flag >= config.host_check_wait:
                self.redis_log_client.hset(current_uuid,"exit_code","timeout")
                self.exe_next=False
            elif self.redis_log_client.hget(current_uuid,"exit_code"):
                self.exe_next=False
            else:
                self.redis_log_client.hset(current_uuid,"exit_code","0")
        else:
            self.redis_log_client.hset(current_uuid,"exit_code","host null")
            self.exe_next=False
        
        if not self.redis_log_client.hget(current_uuid,"stderr"):
            self.redis_log_client.hset(current_uuid,"stderr","")
        if not self.redis_log_client.hget(current_uuid,"stdout"):
            self.redis_log_client.hset(current_uuid,"stdout","")
        

    def __var_exe(self,cmd,current_uuid,var_prefix):
        """
        global.xx="..." select.yy="..." 命令的实际执行
        """
        g_field=cmd.split("=")[0].strip().split(var_prefix+".")[1].strip()         #变量名
        #g_field=cmd.split("=")[0].lstrip(config.prefix_global+".").strip()         #变量名 会去除额外的字符
        #g_value=cmd.lstrip(cmd.split("=")[0]+"=")                  #变量值 会去除额外的字符
        g_value=cmd.split(cmd.split("=")[0]+"=")[1]                 #变量值
        
        os_type = platform.system()

        #存在`shell_command` 则分发到主机
        if (re.match(".*`.+`.*",g_value) and os_type == "Linux") or (re.match(".*%.+%.*",g_value) and os_type == "Windows"):

            tmp_cmd="echo %s" % (g_value)

            g_value=self.__single_exe(self.current_host,tmp_cmd,current_uuid)
   
        return g_field,g_value
        

    def __global_var(self,cmd,current_uuid):
        """
        对于如 global.xx=`${cmd_exe}` 全局参数的设置
        """
        g_field,g_value = self.__var_exe(cmd,current_uuid,config.prefix_global)
        #脚本全局变量保存 可以在执行脚本结束后清空        
        self.redis_tmp_client.hset(self.global_key,g_field,g_value)
    
    
    def __select_var(self,cmd,current_uuid):
        """
        对于如 select.xx=`${cmd_exe}` 参数的设置
        """
        g_field,g_value = self.__var_exe(cmd,current_uuid,config.prefix_select)
        
        key_select_all=config.prefix_select+"_all"+config.spliter+current_uuid
        key_select=config.prefix_select+config.spliter+current_uuid
        #使用临时变量存放
        self.redis_send_client.set(key_select_all,g_value)
        self.redis_send_client.expire(key_select_all, config.tmp_config_expire_sec)
        #阻塞等待
        self.redis_log_client.hset(current_uuid,"step","waiting select")
        block_tag=self.redis_send_client.blpop(key_select, config.tmp_config_expire_sec)
        self.redis_send_client.delete(key_select_all)
        
        if block_tag:
            s_value=str(block_tag[-1])
            self.redis_tmp_client.hset(config.prefix_select+config.spliter+self.cluster_id,g_field,s_value)
            self.redis_log_client.hset(current_uuid,"step","SELECT: "+s_value)
            return 1
        else:
            #超时
            self.redis_log_client.hset(current_uuid,"step","wait select timeout")
            return 0


    def __check_result(self,c_uuid_list,check_result_block=True,ignore_last_err=False):
        """
        阻塞获取命令的执行结果
        用于控制playbook执行的顺序 以及判定是否终止执行playbook
        """ 
        
        r_list=[] 
        for c_uuid in c_uuid_list:
            r={}
            #是否阻塞以检查结果
            if check_result_block:
                
                continue_check=True
                while continue_check:
                    if self.redis_send_client.get(self.kill_key):
                        #可能存在kill操作
                        self.redis_send_client.expire(self.kill_key,config.kill_cluster_expire_sec)
                        self.exe_next=False
                        continue_check=False
                        ignore_last_err=True
                        r["stdout"]=""
                        r["stderr"]=""
                        r["exit_code"]="kill"
                        logger.info("get kill signal in <%s %s> %s" % (self.target,self.cluster_id,c_uuid))
                    else:
                        r=self.redis_log_client.hgetall(c_uuid)
                        #有退出码则认为命令执行结束
                        if "exit_code" in r:
                            
                            continue_check=False
                        else:
                            continue_check=True
           
            else:
                ignore_last_err=True        #不检测结果 则恒忽略此步的执行结果以继续下一步操作
                r["stdout"]=""
                r["stderr"]=""
                r["exit_code"]="0"
           
            r_list.append(r) 

        #如果此步出错，是否继续执行
        if not ignore_last_err:
            for r in r_list:
                if r["stderr"] or str(r["exit_code"])!="0":
                    self.exe_next=False
        
        logger.debug("check result %s <%s %s>" % (str(r_list),self.target,self.cluster_id))
        return r_list


