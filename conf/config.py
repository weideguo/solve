# -*- coding: utf-8 -*-

import os
import ast
import configparser


#根路径
base_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def getcp(config_file=None):
    cp = configparser.ConfigParser()
    if not config_file:
        config_file=os.path.join(os.path.dirname(os.path.abspath(__file__)),"config.conf")
    cp.read(config_file)
    return cp

cp=getcp()


def get_config(section, option, default=None):
    if cp.has_section(section) and cp.has_option(section, option):
        return cp.get(section, option)
    else:
        return default

def get_redis_config(section):
    """
    将每个section的配置信息转成dict
    """
    db=int(cp.get(section,"db"))
    password=cp.get(section,"password")
    sentinels=[]
    service_name=""
    host=""
    port=0
    try:
        #sentinels=eval(cp.get(section,"sentinels"))
        sentinels=ast.literal_eval(cp.get(section,"sentinels"))
        service_name=cp.get(section,"service_name")
        return {"db":db,"password":password,"sentinels":sentinels,"service_name":service_name}
    except:    
        host=cp.get(section,"host")
        port=int(cp.get(section,"port"))
        return {"db":db,"password":password,"host":host,"port":port}


redis_send = get_redis_config("redis_send")
redis_log = get_redis_config("redis_log")
redis_tmp = get_redis_config("redis_tmp")
redis_config = get_redis_config("redis_config")
redis_job = get_redis_config("redis_job")


###################################################################################################
#是否为proxy模式
PROXY=int(get_config("proxy","proxy",0))
proxy_tag="proxy"                                      #用于标记主机为proxy以及proxy广播用的key
proxy_mark=str(get_config("proxy","mark",""))          #默认使用proxy的ip，处于多网卡环境时可能需要手动设置

###################################################################################################
#web服务没有安全认证机制，请不要对外网开放        
#是否启动web服务提供文件管理，服务位于 core.fileserver
bind=get_config("fileserver","bind")                   #web服务监听的网络 
port=get_config("fileserver","port")                   #web服务监听的端口
origin=get_config("fileserver","origin")               #Access-Control-Allow-Origin 允许访问的域，前后端分离时必须要设置

if bind and port and origin:
    bind=str(bind)     
    port=int(port)     
    origin=str(origin) 
    fileserver=True
else:
    fileserver=False

###################################################################################################
aes_key=str(get_config("common","aes_key"))

local_ip_list=[ h.strip() for h in str(get_config("common","local_ip_list")).split(",") ]
#local_ip_list=["127.0.0.1","localhost"]                       

###################################################################################################
#远端主机实现模块
remote_model="core.plugin.ssh.remote_host.RemoteHost" 
#remote_model="core.plugin.ssh2.remote_host.RemoteHost" 
#remote_model="core.plugin.salt.salt_conn.SaltConn"     

"""
模块的类中至少要实现方法forever_run()以供上层调用

可以每个实例化后的对象对应一个远端主机                       
也可以通过判断只实例化一个对象进行命令分发协调 单例模式      

core.plugin.ssh.remote_host.RemoteHost                使用ssh实现 保持连接
core.plugin.ssh2.remote_host.RemoteHost               使用ssh单例模式实现 不保持连接
core.plugin.salt.salt_conn.SaltConn                   使用salt单例模式实现，首次启动前需要通过链接设置salt上传/下载目录与主机目录的映射
                                                      #python 2.7 / salt 2018.3.3 (Oxygen)
"""

###################################################################################################
log_level=10                        #参考logging模块的值 logging.DEBUG=10 logging.INFO=20

remote_process=3                    #使用多少个进程创建远程连接。进程之间竞争从队列获取创建信息以创建远程对象。不会影响实际并发数，设置跟cpu核心一致以便最大限度使用cpu。
max_concurrent_thread=3             #单个主机的最大并发数  
max_concurrent_all=100              #使用单利模式的远端主机实现时生效，这个参数应该设置大一些，每个进程的线程控制
max_localhost_thread=20             #本地模式运行时的最大并发数

                                    #以下都是对于单个redis db而言，n个db的实际数量要乘n
shared_redis_pool_size=30           #主进程redis的连接池的大小  用于连接管理 任务管理等 
localhost_redis_pool_size=10        #本地连接redis的连接池的大小   
remote_host_redis_pool_size=5       #远程连接redis的连接池的大小   
cluster_redis_pool_size=5           #每个执行对象执行时的连接池


clear_start=1                       #启动时清除 连接队列 未执行命令 心跳
host_start_without_cmd=True         #使用单利模式的远端主机实现时应该为False 创建连接时不能存在命令队列

cmd_log_expire_sec=60*60*24         #单条命令日志的保存时间 默认时间单位都为秒
kill_cluster_expire_sec=60          #kill_<cluster id>键的保存时间
closing_host_flag_expire_sec=10     #closing_<ip>键的保存时间
initing_host_flag_expire_sec=3*60   #initing_<ip>键的保存时间 防止在连接后到执行一个命令期间被关闭
tmp_config_expire_sec=60*60*24      #运行对象复制 globa_ session_ key的保存时间
wait_exit_code=100                  #执行wait命令时遇到终止命令的退出状态码

put_wait_time=1                     #上传文件单次判断等待时间
put_wait=60*60                      #上传文件等待次数 如果存在其他上传 则等待
heart_beat_interval=10              #主机心跳间隔
host_check_time=1                   #检查主机连接状态的时间间隔
host_check_wait=5*60                #检查主机连接次数 超过则终止
host_check_success_time=15          #heart_beat时间差小于此判断连接成功 使用salt时这个至应该大一些 因为更新的间隔可能大于heart_beat_interval
host_close_time=8*60*60             #没有执行一段时间后则关闭连接
host_close_check_interval=60*60     #检查是否关闭连接的时间间隔

is_copy_by_link=1                   #是否使用软链接代替复制
spliter="@@@@@"                     #所有与uuid的分隔符   如cmd+spliter+uuid 日志 target


#######################################################################################################
#redis_config
prefix_realhost="realhost_"         #用于创建连接的主机的key开头

#redis_tmp
prefix_global="global"              #全局变量对应的key开头 playbook中全局变量的开头 全局变量如 global.yyy
prefix_session="session"            #输入变量对应的key开头 playbook中全局变量的开头 全局变量如 global.yyy
prefix_select="select"              #输入变量对应的key开头 playbook中全局变量的开头 全局变量如 select.yyy

#redis_log
prefix_sum="sum_"                   #每次每个执行对象所执行的汇总
prefix_log_target="log_target_"     #每个执行对象执行命令的队列key
prefix_log_host="log_host_"         #log_host_<host ip> 每个主机的执行信息
prefix_put="put_"                   #put_<host ip> 存储已经上传文件的信息
prefix_log_job="log_job_"           #每个任务的日志信息

#redis_send
prefix_kill="kill_"                 #key_<cluster id>  终止执行对象的key
prefix_cmd="cmd_"                   #cmd_<host ip>   对主机分发的命令 cmd+spliter+c_uuid     
prefix_heart_beat="heart_beat_"     #heart_beat_<host ip>  主机心跳的key
prefix_check_flag="check_flag_"     #check_flag_<host ip>  是否可以检查存在连接  已经存在则不可再次检查
prefix_initing="initing_"           #正在创建连接的标识
prefix_closing="closing_"           #标记正在关闭 closing_<host ip>
prefix_block="block_"               #block_<cluster id> 标记制定对象逐行阻塞执行 list类型，插入0正常运行被阻塞的命令然后阻塞，-1则结束阻塞之后的命令按顺序执行，其他则终止当前被阻塞的以及之后的

pre_close="close_"                  #插入key_conn_control中       关闭连接 close_<ip>  
key_conn_control="conn_control"     #控制主机连接与断开的队列key  建立连接 <ip> 
key_kill_host="kill_host"           #用于分发关闭主机的publish
key_job_list="job_list"             #执行任务的队列

#redis_job
prefix_job="job_"                   #每个任务的信息 job_<job id> 插入 key_job_list 


#######################################################################################################
#禁止执行的命令 添加时请务必使用函数 re.match(cmd_pattern,cmd) 先行验证 
#正则表达式，错误信息，退出码（等同于执行shell命令后的退出码）
deny_commands=[
("(.*(\s|\||;|&|\`)+|)rm\s+.*/(\s+.*|\||;|&||`$)", "too danger to execute", 1),    #带有 "rm /" 的命令
(".*eval.*", "too danger to execute", 1),                                          #带有eval 的命令 
(".*e(\'|\")*v(\'|\")*a(\'|\")*l.*", "too danger to execute", 1),                  #通过单引号 双引号拼接成eval                        #``中带有rm的命令
]

#只能适合常规的正则匹配
#通过变量拼接绕过限制
# a="e";b="val" && $a$b "who"  
#
