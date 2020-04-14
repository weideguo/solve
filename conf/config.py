#coding:utf8

#redis_send
redis_send={
"db": 0,
"password": "my_redis_passwd",
"host": "127.0.0.1",                                                                  #使用sentinel则这个不必设置
"port": 6379,                                                                         #使用sentinel则这个不必设置
"service_name": "mymaster",                                                          #是否使用sentinel
"sentinels": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)],       #是否使用sentinel
}

#redis_log
redis_log={
"db": 1,
"password": "my_redis_passwd",
"host": "127.0.0.1",         
"port": 6379,                
"service_name": "mymaster",                                                         
"sentinels": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)]      
}

#redis_tmp
redis_tmp={
"db": 2,
"password": "my_redis_passwd",
"host": "127.0.0.1",         
"port": 6379,                
"service_name": "mymaster",                                                         
"sentinels": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)]     
}

#redis_job
redis_job={
"db": 14,
"password": "my_redis_passwd",
"host": "127.0.0.1",         
"port": 6379,                
"service_name": "mymaster",                                                         
"sentinels": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)]       
}

#redis_config
redis_config={
"db": 15,
"password": "my_redis_passwd",
"host": "127.0.0.1",         
"port": 6379,                
"service_name": "mymaster",                                                         
"sentinels": [('127.0.0.1', 26479),('127.0.0.1', 26480),('127.0.0.1', 26481)]     
}


###################################################################################################
#设置根路径
import os
base_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
###################################################################################################

remote_model="core.plugin.ssh.remote_host.RemoteHost" #远端主机实现模块
#remote_model="core.plugin.salt.salt_conn.SaltConn"     
"""
模块的类中
__init__(self,host_info,redis_send_pool,redis_log_pool) 接受的三个参数：主机的信息(dict) 接受命令的redis连接池 执行结果存放的redis连接池
至少要实现方法forever_run()以供上层调用

可以每个实例化后的对象对应一个远端主机                        使用ssh分发命令时使用该方法
也可以通过判断只实例化一个对象进行命令分发协调 单例模式       使用salt分发命令时使用该方法


core.plugin.ssh.remote_host.RemoteHost                使用ssh实现
core.plugin.salt.salt_conn.SaltConn                   使用salt实现,首次启动前需要通过链接设置salt上传/下载目录与主机目录的映射
                                                      #python 2.7 / salt 2018.3.3 (Oxygen)
"""

###################################################################################################
#是否为proxy模式 不设置默认为master 
#在启动时可以在命令行指定为proxy或master，优先级为：命令行>配置文件>master模式
#PROXY=False
proxy_tag="proxy"                   #用于标记主机为proxy以及proxy广播用的key
proxy_mark=""                       #默认使用proxy的ip，处于多网卡环境时可能需要手动设置
#proxy_mark="AAA"                   #不一定使用ip，最好每个proxy唯一，如果相同则竞争处理（这是正常的）

#使用proxy管理的主机
#<proxy_tag>:<proxy_mark>:<host_ip>
###################################################################################################
#web服务没有安全认证机制，请不要对外网开放
#fileserver=True           #是否启动web服务提供文件管理，服务位于 core.fileserver
bind="127.0.0.1"            #web服务监听的网络 
port=9000                 #web服务监听的端口
origin="*"                #Access-Control-Allow-Origin 允许访问的域，前后端分离时必须要设置

###################################################################################################



clear_start=1                       #启动时清除 连接队列 未执行命令 心跳
heart_beat_interval=10              #主机心跳间隔
max_concurrent_thread=3             #单个主机的最大并发数
cmd_log_expire_sec=60*60*24         #单条命令日志的保存时间 默认时间单位都为秒
kill_cluster_expire_sec=60          #kill_<cluster id>键的保存时间
closing_host_flag_expire_sec=10     #closing_<ip>键的保存时间
initing_host_flag_expire_sec=3*60   #initing_<ip>键的保存时间 防止在连接后到执行一个命令期间被关闭
tmp_config_expire_sec=60*60*24      #运行对象复制 globa_ session_ key的保存时间
wait_exit_code=100                  #执行wait命令时遇到终止命令的退出状态码

put_wait_time=1                     #上传文件单次判断等待时间
put_wait=60*60                      #上传文件等待次数 如果存在其他上传 则等待

host_check_time=1                   #检查主机连接状态的时间间隔
host_check_wait=5*60                #检查主机连接次数 超过则终止
host_check_success_time=15          #heart_beat时间差小于此判断连接成功
#host_check_success_time=60          #使用salt时这个至应该大一些 因为更新的间隔可能大于heart_beat_interval

host_close_time=8*60*60             #没有执行一段时间后则关闭连接
host_close_check_interval=60*60     #检查是否关闭连接的时间间隔

is_copy_by_link=1                   #是否使用软链接代替复制

spliter="@@@@@"                     #所有与uuid的分隔符   如cmd+spliter+uuid 日志 target

local_ip_list=["127.0.0.1","localhost"]  #标记为本地地址，对本地的命令将使用本地模式运行，而不是通过ssh
max_localhost_thread=20                  #本地模式运行时的最大并发数

#######################################################################################################
#redis_config
prefix_realhost="realhost_"         #用于创建连接的主机的key开头
prefix_global="global"              #全局变量对应的key开头 playbook中全局变量的开头 全局变量如 global.yyy
prefix_session="session"            #输入变量对应的key开头 playbook中全局变量的开头 全局变量如 global.yyy

#playbook_prefix_global="global"     #playbook中全局变量的开头 全局变量如 global.yyy
#playbook_prefix_session="session"   #playbook中全局变量的开头 全局变量如 global.yyy

#redis_log
prefix_sum="sum_"                   #每次每个执行对象所执行的汇总
prefix_log_target="log_target_"   #每个执行对象执行命令的队列key
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

pre_close="close_"                  #插入key_conn_control中       关闭连接 close_<ip>  
key_conn_control="conn_control"     #控制主机连接与断开的队列key  建立连接 <ip> 
key_kill_host="kill_host"           #用于分发关闭主机的publish
key_job_list="job_list"             #执行任务的队列

#redis_job
prefix_job="job_"                   #每个任务的信息 job_<job id> 插入 key_job_list 

