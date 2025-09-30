# -*- coding: utf-8 -*-
import os
import re
import uuid
import time
import platform 
from threading import Thread
from traceback import format_exc

from jinja2 import Template

from .playbook_parser import simple_parser
from lib.utils import safe_decode,cmd_split,cmd_options_split
from lib.wrapper import logger,logger_err,password
from lib.redis_conn import RedisConn
from lib.myssh import MySSH 
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
        
        self.connect_host_info={}         #cluster涉及到的连接
        
        
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
        pattern = r'^(%s|%s|%s)\s*\..*' % (config.prefix_global,config.prefix_session,config.prefix_select)
        
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
        
        #通过uuid关闭cluster涉及的连接
        for host in self.connect_host_info:
            host_uuid=self.connect_host_info[host]
            self.redis_send_client.publish(config.key_kill_host,host_uuid) 
        
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
        data = {}
        # .被jinja2特殊使用 因此使用__SOLVE_INNER_KEEP__临时替代
        sove_inner_keep = "__SOLVE_INNER_KEEP__"

        # 处理形如 {{abc{{session.user}}ABC}} 的特殊jinja变量
        for c_ in re.findall(r"(?<={{)[^{}]*?{{[^{}]+?}}[^{}]*?(?=}})",cmd): 
            full_matches = re.findall(r"(?<={{).+?(?=}})",c_)
            c = full_matches[0] # 有且仅有一个匹配
            v = password.decrypt(safe_decode(self.get_value(target,c)))
            if not v:
                # 双重渲染第一次的值不因该为空
                raise Exception("variable [%s] render error, double render value should not empty" % c)
            # 直接进行替换
            cmd = cmd.replace("{{%s}}" % c, v)
        
        # 处理普通的jinja变量
        for c in re.findall(r"(?<={{).+?(?=}})",cmd):
            c_r = re.sub(r"\s*\.\s*",sove_inner_keep,c).strip()      #去除字符串的左右空格 以及.左右的空格
            cmd = cmd.replace("{{%s}}" % c, "{{%s}}" % c_r)
            data[c_r] = password.decrypt(safe_decode(self.get_value(target,c)))
        
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
                self.redis_log_client.hset(self.current_uuid,"step","pausing")
                block_tag=self.redis_send_client.blpop(key, timeout=config.tmp_config_expire_sec)
                self.redis_log_client.hdel(self.current_uuid,"step")
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
            current_line=0
            for next_cmd in simple_parser(playbook):
                current_line=current_line+1
                if not self.exe_next:
                    break
                
                #去除所有命令的左右空格以及换行符，并转换成unicode格式
                next_cmd=next_cmd.strip()
                next_cmd=safe_decode(next_cmd)
                
                self.current_uuid=uuid.uuid1().hex
                if current_line < begin_line:
                    #主机切换的命令正常运行
                    if re.match(r"^\[.*\]$",next_cmd):
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
                        self.redis_log_client.hset(self.current_uuid,"stderr",format_exc())
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
                    if re.match(r"^\[.*\]$",cmd):
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
                    elif re.match(r"^"+config.prefix_global+r"\..+=",cmd):
                        self.__global_var(cmd,self.current_uuid)
                    
                    #选择变量设置
                    #elif re.match("^select\..+=",cmd):
                    elif re.match(r"^"+config.prefix_select+r"\..+=",cmd):
                        if not self.__select_var(cmd,self.current_uuid):
                            self.exe_next=False
                            stop_str="select failed"
                            break
                    
                    #文件传输
                    elif re.match(r"^__sync__ ",cmd):
                        try:
                            self.__sync_exe(cmd)
                        except Exception as e:
                            logger_err.error(format_exc())
                            self.redis_log_client.hset(self.current_uuid,"exit_code","scp error")
                            #self.redis_log_client.hset(self.current_uuid,"stderr",format_exc())
                            self.redis_log_client.hset(self.current_uuid,"stderr",str(e))
                            self.redis_log_client.hset(self.current_uuid,"stdout","")
                            break
                    
                    #普通命令 简单的shell命令
                    else:
                        self.__single_exe(self.current_host,cmd,self.current_uuid)
                
                    self.redis_log_client.hset(self.current_uuid,"stop_timestamp",time.time())
    
                #从redis获取信息，判断是否进行kill操作以终止之后的命令
                if self.redis_send_client.get(self.kill_key):        
                    self.redis_send_client.expire(self.kill_key,config.kill_cluster_expire_sec)
                    self.exe_next=False
                    logger.info("get kill signal in <%s %s>" % (self.target,self.cluster_id))
                    stop_str="killed" 
                
                self.redis_log_client.expire(self.current_uuid,config.cmd_log_expire_sec)
            
            last_uuid=self.current_uuid
            
            if self.exe_uuid_list:
                #执行到最后一行存在后台命令 则默认运行一次wait
                self.__single_exe(host="",cmd="wait",c_uuid="")

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
        
        if config.cluster_connect_control:
            if self.redis_send_client.exists(config.prefix_heart_beat+host):
                #有连接的先用已经存在的连接 用于兼容本地连接
                exe_tag=host
            else:
                exe_tag=self.connect_host_info[host]
        else:
            exe_tag=host
        
        logger.debug("-------------- <%s %s> %s %s %s accept" % (self.target,self.cluster_id,host,cmd,c_uuid))
        
        if re.match("^wait$",cmd.strip()):
            #对wait命令特殊处理
            check_result_block=True
            self.__check_result(self.exe_uuid_list)
            self.redis_log_client.hset(self.current_uuid,"stderr","")
            if self.exe_next==False:
                self.redis_log_client.hset(self.current_uuid,"exit_code",config.wait_exit_code)
                self.redis_log_client.hset(self.current_uuid,"stderr","wait command result check failed")
            else:
                self.redis_log_client.hset(self.current_uuid,"exit_code",0)    
            #self.redis_log_client.expire(self.current_uuid,config.cmd_log_expire_sec)
            self.exe_uuid_list=[]
            r=""
        elif re.match(r".*&$",cmd.strip()):
            #特殊处理如   shell command &   
            #print self.exe_uuid_list
            self.exe_uuid_list.append(c_uuid)
            check_reault_block=False 
            #print c_uuid,self.exe_uuid_list,self.target 
            cmd = re.sub(r"&\s*?$","",cmd)
            self.redis_send_client.rpush(config.prefix_cmd+exe_tag,cmd+config.spliter+c_uuid)
            r=""
        else:        
            self.redis_send_client.rpush(config.prefix_cmd+exe_tag,cmd+config.spliter+c_uuid)        
            r=self.__check_result([c_uuid])[0]["stdout"].replace("\n","")   
 
        logger.debug("-------------- <%s %s> %s %s %s complete" % (self.target,self.cluster_id,host,cmd,c_uuid))        

        return r    


    def __host_conn(self,current_host,current_uuid):
        if config.cluster_connect_control: 
            if current_host not in self.connect_host_info:
                #cluster控制连接与关闭时，只有之前没创建的连接才创建
                self.connect_host_info[current_host]=current_uuid
                self.redis_send_client.rpush(config.key_conn_control,current_host+config.spliter+current_uuid)
        else:
            #将主机ip放入初始化队列 由其他线程后台初始化连接
            self.redis_send_client.rpush(config.key_conn_control,current_host+config.spliter+current_uuid)
    
    
    def __host_change(self,cmd,current_uuid):
        """
        将连接信息插入队列 控制主机的连接 并切换当前接受命令的主机        
        """
        #self.current_host=cmd.replace("[","").replace("]","").strip()
        self.current_host=cmd.strip()[1:-1].strip()
        
        if self.current_host:
            
            self.__host_conn(self.current_host,current_uuid)
            self.redis_log_client.hset(current_uuid,"uuid",current_uuid)

            #阻塞到host启动完毕
            def get_heart_beat():
                heart_beat=self.redis_send_client.get(config.prefix_heart_beat+current_uuid) or 0
                #用于兼容本地连接
                heart_beat1=self.redis_send_client.get(config.prefix_heart_beat+self.current_host) or 0
                return heart_beat or heart_beat1

            retry_flag=0
            #while time.time()-float(get_heart_beat())>config.host_check_success_time and retry_flag<config.host_check_wait \
            #      and self.exe_next and (not self.redis_log_client.hget(current_uuid,"exit_code")):
            #存在心跳即可 不必判断时间？
            while not float(get_heart_beat()) and retry_flag<config.host_check_wait \
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

        #存在`shell_command` $(shell_command) 则分发到主机
        if (os_type == "Linux" and (re.match(r".*`.+`.*",g_value) or re.match(r".*\$\(.+\).*",g_value) ) ) or \
           (os_type == "Windows" and re.match(r".*%.+%.*",g_value) ):

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
        self.redis_send_client.set(key_select_all,g_value, config.tmp_config_expire_sec)
        #self.redis_send_client.expire(key_select_all, config.tmp_config_expire_sec)
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
                            # 防止检查频率过高
                            time.sleep(config.command_check_interval)
           
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


    def __path_info(self, exe_host, full_path):
        cmd = "ls -ld %s" % full_path
        r = self.__single_exe(exe_host,cmd)
        if r:
            if r[0]=="-":
                return "file"
            elif r[0]=="d":
                return "dir"
            elif r[0]=="l":
                return "link"         # 软链接，硬链接当成普通文件对待
            else:
                return "undefine"
        else:
            # 路径不存在时
            return ""
        
    
    def __get_path_size(self, exe_host, full_path):
        cmd = "du -sb %s" % full_path
        r = self.__single_exe(exe_host,cmd)
        size  = r.split("\t")[0]
        return size

    
    def __sync_exe(self,cmd_line):
        # __sync__ /from_file_or_dir to_host:/to_dir   # 使用realhost的名字而不是ip，因此可以带tag
        # __sync__ /from_file_or_dir to_host:/to_dir  -compress=1 -try=4 -proxy=10.0.0.1 -bwlimit=10m -partial=1 -check=1 --progress=1 -batch=524288
        # __sync__ from_host:/from_file_or_dir /to_dir
        _cmd = cmd_split(cmd_line,3)
        
        is_compress = True
        try_seq = "1234"
        proxy_host = ""
        bwlimit = ""
        is_partial = True
        is_check = False
        is_progress = True
        batch_size = 512*1024
        
        if len(_cmd) < 3:
            raise Exception("__sync__ command length must not less than 3")
        elif len(_cmd) == 4:
            cmd_options = cmd_options_split(_cmd[3])
            is_compress = int(cmd_options["compress"])==1 if "compress" in cmd_options else is_compress  
            try_seq = cmd_options["try"] if "try" in cmd_options else try_seq
            proxy_host = cmd_options["proxy"] if "proxy" in cmd_options else proxy_host
            bwlimit = cmd_options["bwlimit"] if "bwlimit" in cmd_options else bwlimit
            is_partial = int(cmd_options["partial"])==1 if "partial" in cmd_options  else is_partial
            is_check = int(cmd_options["check"])==1 if "check" in cmd_options else is_check
            is_progress = int(cmd_options["progress"])==1 if "progress" in cmd_options else is_progress
            batch_size = int(cmd_options["batch"]) if "batch" in cmd_options else batch_size
        
        if bwlimit and not re.match(r"\d+\.?\d*[kmg]$",bwlimit):
            raise Exception("__sync__ bwlimit format error")
        
        current_host = self.current_host
        from_info = _cmd[1].split(":")
        if len(from_info) > 2:
            raise Exception("__sync__ from_info format error")
        if len(from_info) == 2:
            from_host = from_info[0]
            from_file_or_dir = from_info[1]
            remote_host = from_host
        else:
            from_host =  current_host
            from_file_or_dir = from_info[0]
        
        to_info = _cmd[2].split(":")        
        if len(to_info) > 2:
            raise Exception("__sync__ to_info format error")
        elif len(to_info) == 2:
            to_host = to_info[0]
            to_dir = to_info[1]
            remote_host = to_host
        else:
            to_host =  current_host
            to_dir = to_info[0]
        
        from_dir = os.path.dirname(from_file_or_dir)
        from_base = os.path.basename(from_file_or_dir)
        to_full = os.path.join(to_dir,from_base)
        
        logger.debug("from_host [%s] to_host [%s] current_host [%s] remote_host [%s]" % (from_host,to_host,self.current_host,remote_host))
        
        if (len(to_info) != 2 and len(from_info) != 2) or (len(to_info) == 2 and len(from_info) == 2):
            raise Exception("__sync__ from_info or to_info format error")
        
        if from_host == to_host:
            exit_code = 0
            stderr = ""
            stdout = "from_host same as to_host"
            if to_dir[-1] == "/":
                to_dir = to_dir[:-1]
            
            if from_dir != to_dir:
                exit_code = 1
                stderr = "from_dir [%s] not same as to_dir [%s]" % (from_dir,to_dir)
                self.exe_next = False
                
            self.redis_log_client.hset(self.current_uuid,"exit_code",exit_code)
            self.redis_log_client.hset(self.current_uuid,"stderr",stderr)
            self.redis_log_client.hset(self.current_uuid,"stdout",stdout)
            return
        
        from_passwd = password.decrypt(safe_decode(self.redis_config_client.hget(config.prefix_realhost+from_host,"passwd")))
        from_user = safe_decode(self.redis_config_client.hget(config.prefix_realhost+from_host,"user"))
        from_ip = safe_decode(self.redis_config_client.hget(config.prefix_realhost+from_host,"ip").split("_")[0])    # 这里需要由ip_tag转成ip
        from_ssh_port = safe_decode(self.redis_config_client.hget(config.prefix_realhost+from_host,"ssh_port"))
        
        to_passwd = password.decrypt(safe_decode(self.redis_config_client.hget(config.prefix_realhost+to_host,"passwd")))
        to_user = safe_decode(self.redis_config_client.hget(config.prefix_realhost+to_host,"user"))
        to_ip = safe_decode(self.redis_config_client.hget(config.prefix_realhost+to_host,"ip").split("_")[0])
        to_ssh_port = safe_decode(self.redis_config_client.hget(config.prefix_realhost+to_host,"ssh_port"))
        
        # remote_host 可能还没有连接
        self.__host_change("[%s]" % remote_host,self.current_uuid)  # 需要检查连接，否则可能出现命令队列先存在
        self.redis_log_client.hdel(self.current_uuid,"exit_code")       # 需要移除主机连接的返回码，否则因为存在返回码导致会执行下一行命令
        self.current_host = current_host       
        
        # 源端只要路径存在即可，可以为链接
        from_path_info = self.__path_info(from_host,from_file_or_dir)
        if not from_path_info:
            raise Exception("__sync__ from_file_or_dir not exists")
        
        # 目标端必须为路径，不支持软链接
        to_path_info = self.__path_info(to_host,to_dir)
        if not to_path_info:
            raise Exception("__sync__ to_dir not exists") 
        elif to_path_info not in ["dir"]:
            raise Exception("__sync__ to_dir not a dir") 
        
        is_from_file = from_path_info == "file"
        
        from_size = self.__get_path_size(from_host,from_file_or_dir)
        self.redis_log_client.hset(self.current_uuid,"total_size",from_size)
        
        rsync_option = "-av"
        tar_option = ""
        ssh_proxy_pv = ""
        if is_compress:
            rsync_option = rsync_option+"z"
            tar_option = tar_option+" -z"
        if is_partial:
            rsync_option = rsync_option+" --partial"
        
        if bwlimit:
            rsync_option = rsync_option+" --bwlimit="+bwlimit
            if not ssh_proxy_pv:
                ssh_proxy_pv = " | pv "
            
            ssh_proxy_pv = ssh_proxy_pv + " -L "+bwlimit

        #ssh_proxy_progress = ""
        if is_progress:
            rsync_option = rsync_option+" --progress"
            
            if not ssh_proxy_pv:
                ssh_proxy_pv = " | pv "
            
            _from_size = int(from_size)
            if _from_size > 100*1024*1024*1024:
                interval = 5*60
            elif _from_size > 10*1024*1024*1024:
                interval = 60
            elif _from_size > 1024*1024*1024:
                interval = 5
            elif _from_size > 100*1024*1024:
                interval = 2
            else:
                interval = 1
            ssh_proxy_pv = ssh_proxy_pv + " -nb -i %s" % interval    
 
        
        # 使用交互方式输入密码？
        def __scp__(exe_host, from_host, real_try):
            # 在current_host运行 
            real_try = real_try+1
            self.redis_log_client.hset(self.current_uuid,"sync_desc","count:%s" % real_try)
            logger.debug("from_host [%s] to_host [%s] current_host [%s] remote_host [%s] exe_host [%s]" % (from_host,to_host,self.current_host,remote_host,exe_host))
            if exe_host == from_host:
                # 执行命令的主机为文件存放的主机
                cmd_scp = """rsync %s --rsh='sshpass -p "%s" ssh -oStrictHostKeyChecking=no -p %s' %s %s@%s:%s""" % \
                                      (rsync_option,to_passwd,to_ssh_port,from_file_or_dir,to_user,to_ip,to_dir)
            else:
                cmd_scp = """rsync %s --rsh='sshpass -p "%s" ssh -oStrictHostKeyChecking=no -p %s' %s@%s:%s %s""" % \
                                      (rsync_option,from_passwd,from_ssh_port,from_user,from_ip,from_file_or_dir,to_dir)
                
            logger.debug("transfer command: [%s] to [%s] ------------ <%s %s> %s" % (cmd_line,cmd_scp,self.target,self.cluster_id,self.current_uuid))
            
            self.__single_exe(exe_host,cmd_scp,self.current_uuid)
            scp_result = self.__check_result([self.current_uuid])[0]
            self.current_host = current_host 
            return scp_result,cmd_scp,real_try
            
        
        def __scp_current(real_try):
            # 在current_host运行 
            return __scp__(self.current_host,from_host,real_try)
        
        def __scp_remote(real_try):
            # 在remote_host运行 
            return __scp__(remote_host,from_host,real_try)
        
        def __scp_proxy(real_try):
            # 在solve运行的机器上执行，因为solve可以连接两台服务器，从而可以实现代理
            real_try = real_try+1
            self.redis_log_client.hset(self.current_uuid,"sync_desc","count:%s" % real_try)
            
            cmd_localhost = """sshpass -p '%s' ssh -p %s -oStrictHostKeyChecking=no %s@%s 'cd %s && tar %s -cf - %s' \
                             %s | sshpass -p '%s' ssh -p %s -oStrictHostKeyChecking=no %s@%s 'tar %s -xf - -C %s'""" % \
                            (from_passwd,from_ssh_port,from_user,from_ip,from_dir,tar_option,from_base,\
                             ssh_proxy_pv,to_passwd,to_ssh_port,to_user,to_ip,tar_option,to_dir)
            
            logger.debug("run command: [%s] ------------ <%s %s> %s" % (cmd_localhost,self.target,self.cluster_id,self.current_uuid))
            if proxy_host:
                exe_host = proxy_host
                self.__host_change("[%s]" % exe_host,self.current_uuid)
                self.redis_log_client.hdel(self.current_uuid,"exit_code")
            else:
                exe_host = config.local_ip_list[0]
            self.__single_exe(exe_host,cmd_localhost,self.current_uuid)
            scp_result = self.__check_result([self.current_uuid])[0]     
            self.current_host = current_host                          # __check_result 会修改 self.current_host，因此要重置
            return scp_result,cmd_localhost,real_try

        def __scp_inner(real_try):
            # 使用paramiko传输，效率可能比较低
            # 只能传文件
            # 不支持压缩
            r = {}
            r["stdout"] = ""
            r["stderr"] = ""
            r["exit_code"] = "0"
            if not is_from_file:
                r["stderr"] = "only file can use paramiko sftp module"
                r["exit_code"] = "1"
                self.redis_log_client.hset(self.current_uuid,"exit_code",r["exit_code"])
                self.redis_log_client.hset(self.current_uuid,"stderr",r["stderr"])
                self.redis_log_client.hset(self.current_uuid,"stdout",r["stdout"])
                self.exe_next = False
                self.current_host = current_host
                return r,"",real_try
            
            real_try = real_try+1
            self.redis_log_client.hset(self.current_uuid,"sync_desc","count:%s" % real_try)
            from_file = from_file_or_dir            
            to_file = to_full
            
            from_ssh = MySSH({"ip":from_ip,"ssh_port":from_ssh_port,"user":from_user,"passwd":from_passwd})
            to_ssh = MySSH({"ip":to_ip,"ssh_port":to_ssh_port,"user":to_user,"passwd":to_passwd})
            from_ssh.init_conn()
            to_ssh.init_conn()
            
            cmd_paramiko = "__paramiko_sftp__ %s@%s:%s::%s %s@%s:%s::%s" % (from_user,from_ip,from_ssh_port,from_file,to_user,to_ip,to_ssh_port,to_file)
            self.redis_log_client.hset(self.current_uuid,"cmd",cmd_paramiko)
            
            logger.debug("run command: [%s] ------------ <%s %s> %s" % (cmd_paramiko,self.target,self.cluster_id,self.current_uuid))
            
            from_sftp_client = from_ssh.ssh_client.open_sftp()
            to_sftp_client = to_ssh.ssh_client.open_sftp()
            
            from_file_attr = from_sftp_client.stat(from_file)
            total_size = from_file_attr.st_size                      # 只对文件准确   
            self.redis_log_client.hset(self.current_uuid,"total_size",total_size)
            
            from_seek = 0
            begin_size = 0
            write_mode = "wb"
            if is_partial:
                to_file_attr = to_sftp_client.stat(to_file)
                begin_size = to_file_attr.st_size  
                from_seek = begin_size
                write_mode = "ab"
            
            self.redis_log_client.hset(self.current_uuid,"current_size",begin_size)
            
            # 还是存在读写互相影响
            # todo 改用多线程实现？
            transfer_size = total_size - begin_size
            #batch_size = 512*1024
            show_process_gap = int(transfer_size/(batch_size*20))          # 记录20次已传输大小
            if not show_process_gap:
                show_process_gap = 1
            
            last_data = 0   
            def read_remote():
                with from_sftp_client.file(from_file, "rb") as src_file:
                    src_file.seek(from_seek)
                    while True:
                        data = src_file.read(batch_size)
                        if data:
                            yield data
                        else:
                            break
                
            
            with to_sftp_client.file(to_file, write_mode) as dest_file:
                i = 0
                last_data = ""
                for data in read_remote():
                    if i%show_process_gap == 0:
                        self.redis_log_client.hset(self.current_uuid,"current_size",begin_size+i*batch_size)
                
                    dest_file.write(data)
                    last_data = data
                    i = i+1
                
                self.redis_log_client.hset(self.current_uuid,"current_size",begin_size + (i-1)*batch_size+len(last_data))

            from_ssh.close()
            to_ssh.close()
            
            logger.debug("run command: [%s] success ------------ <%s %s> %s" % (cmd_paramiko,self.target,self.cluster_id,self.current_uuid))
            
            self.redis_log_client.hset(self.current_uuid,"exit_code",r["exit_code"])
            self.redis_log_client.hset(self.current_uuid,"stderr",r["stderr"])
            self.redis_log_client.hset(self.current_uuid,"stdout",r["stdout"])
            self.current_host = current_host
            return r,cmd_paramiko,real_try
        
        
        self.redis_log_client.hset(self.current_uuid,"cmd_type","EXTEND")  
        real_try = 0
        scp_functions = [__scp_current,__scp_remote,__scp_proxy,__scp_inner]
        
        _try_seq = []
        for s in try_seq:
            if int(s) in range(1,1+len(scp_functions)):
                _try_seq.append(int(s)-1)
            else:
                raise Exception("number in arg [try] should in %s" % list(range(1,1+len(scp_functions))))
        
        for s in _try_seq:
            scp_function = scp_functions[s]
            self.redis_log_client.hdel(self.current_uuid,"exit_code")
            self.redis_log_client.hset(self.current_uuid,"stderr","")         # 将之前可能存在的stderr置为空，以免出现当前执行正确但存在之前的stderr
            scp_result,cmd_real,real_try = scp_function(real_try)
        
            if scp_result["exit_code"] in [0,"0"]:
                logger.debug("run command: [%s] success ------------ <%s %s> %s" % (cmd_real,self.target,self.cluster_id,self.current_uuid))
                
                to_size = self.__get_path_size(to_host,to_full)
                self.redis_log_client.hset(self.current_uuid,"current_size",to_size)
                
                if is_check:
                    if is_from_file:
                        # 为文件时校验MD5
                        from_ssh = MySSH({"ip":from_ip,"ssh_port":from_ssh_port,"user":from_user,"passwd":from_passwd})
                        to_ssh = MySSH({"ip":to_ip,"ssh_port":to_ssh_port,"user":to_user,"passwd":to_passwd})
                        from_ssh.init_conn()
                        to_ssh.init_conn()
                        
                        from_file = from_file_or_dir            
                        to_file = to_full
                        
                        from_sftp_client = from_ssh.ssh_client.open_sftp()
                        to_sftp_client = to_ssh.ssh_client.open_sftp()
                        
                        from_md5 = from_ssh.md5_remote(from_sftp_client,from_file)
                        to_md5 = to_ssh.md5_remote(to_sftp_client,to_file)
                        
                        is_success = 1 if from_md5==to_md5 else 0
                        self.redis_log_client.hset(self.current_uuid, "from_md5",from_md5)
                        self.redis_log_client.hset(self.current_uuid, "to_md5",to_md5)
                        self.redis_log_client.hset(self.current_uuid, "is_success",is_success)
                        if not is_success:
                            self.redis_log_client.hset(self.current_uuid, "exit_code","md5 check failed")
        
                        from_ssh.close()
                        to_ssh.close()
                    else:
                        # 为目录时校验目录大小
                        is_success = 1 if from_size == to_size else 0
                        self.redis_log_client.hset(self.current_uuid, "is_success",is_success)
                        if is_success:
                            self.redis_log_client.hset(self.current_uuid, "exit_code","size check failed")
                
                
                self.exe_next = True
                break
            else:
                logger.debug("run command: [%s] failed [%s] ------------ <%s %s> %s" % (cmd_real,scp_result["stderr"], self.target,self.cluster_id,self.current_uuid))
        
        
        self.redis_log_client.hset(self.current_uuid,"cmd_type","EXTEND")    # 可能因为执行shell命令导致类型被改变，因此再设置一次
        self.current_host = current_host
        