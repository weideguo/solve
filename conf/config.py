#coding:utf8

#redis_send
redis_send_host="127.0.0.1"
redis_send_port=6379
redis_send_passwd="my_redis_passwd"
redis_send_db=0

#redis_log
redis_log_host="127.0.0.1"
redis_log_port=6379
redis_log_passwd="my_redis_passwd"
redis_log_db=1


#redis_job
redis_job_host="127.0.0.1"
redis_job_port=6379
redis_job_passwd="my_redis_passwd"
redis_job_db=14



#redis_config
redis_config_host="127.0.0.1"
redis_config_port=6379
redis_config_passwd="my_redis_passwd"
redis_config_db=15


###################################################################################################

clear_start=1                       #启动时清除 连接队列 未执行命令 心跳
heart_beat_interval=10              #主机心跳间隔
max_concurrent_thread=3             #单个主机的最大并发数
cmd_log_expire_sec=60*60*24         #单条命令日志的保存时间 默认时间单位都为秒
kill_cluster_expire_sec=60          #kill_<cluster id>键的保存时间
closing_host_flag_expire_sec=10     #closing_<ip>键的保存时间
initing_host_flag_expire_sec=3*60   #initing_<ip>键的保存时间 防止在连接后到执行一个命令期间被关闭
copy_config_expire_sec=60*60*24     #运行对象复制key的保存时间
global_var_expire_sec=60*60*24      #global_ 全局变量的保存时间
wait_exit_code=100                  #执行wait命令时遇到终止命令的退出状态码

put_wait_time=1                     #上传文件单次判断等待时间
put_wait=60*60                      #上传文件等待次数 如果存在其他上传 则等待

host_check_time=1                   #检查主机连接状态的时间间隔
host_check_wait=5*60                #检查主机连接次数 超过则终止
host_check_success_time=10          #heart_beat时间差小于此判断连接成功

host_close_time=8*60*60             #没有执行一段时间后则关闭连接
host_close_chech_interval=60*60     #检查是否关闭连接的时间间隔

is_copy_by_link=1                   #是否使用软链接代替复制

cmd_spilter="@@@@@"                 #cmd+cmd_spilter+c_uuid  用于命令与命令id之间的分隔

cluster_spilter=":::"               #用于任务分发时cluster与cluster_id的分隔

#######################################################################################################
#redis_config
prefix_global="global_"             #全局变量对应的key开头
predix_realhost="realhost_"         #用于创建连接的主机的key开头

playbook_prefix_global="global."    #playbook中全局变量的开头

#redis_log
prefix_sum="sum_"                   #每次每个执行对象所执行的汇总
prefix_log_cluster="log_cluster_"   #每个执行对象执行命令的队列key
prefix_log_host="log_host_"         #log_host_<host ip> 每个主机的执行信息
prefix_put="put_"                   #put_<host ip> 存储已经上传文件的信息

#redis_send
prefix_kill="kill_"                 #key_<cluster id>  终止执行对象的key
prefix_cmd="cmd_"                   #cmd_<host ip>   对主机分发的命令 cmd+cmd_spilter+c_uuid     
prefix_heart_beat="heart_beat_"     #heart_beat_<host ip>  主机心跳的key
prefix_check_flag="check_flag_"     #check_flag_<host ip>  是否可以检查存在连接  已经存在则不可再次检查
prefix_initing="initing_"           #正在创建连接的标识
prefix_closing="closing_"           #标记正在关闭 closing_<host ip>

pre_close="close_"                  #插入key_conn_control中       关闭连接 close_<ip>  
key_conn_control="conn_control"     #控制主机连接与断开的队列key  建立连接 <ip> 
key_kill_host="kill_host"           #用于分发关闭主机的publish


#redis_job
prefix_log_job="log_job_"           #每个任务的日志信息
prefix_job="job_"                   #每个任务的信息 job_<job id> 插入 key_job_list 
key_job_list="job_list"             #执行任务的队列
