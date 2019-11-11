# SOLVE #

Simple command deliver server, base on SSH. 

基于SSH实现的命令分发服务, 由redis存储数据，playbook存储命令集合。


running
--------------

### dependency servers ###
* redis (>= 2.0.0)
* salt (使用salt分发时才必须, README_salt.md)

### version support ###
* python 2.7
* python 3.5

### prerun ###
```shell
#set config
vim conf/config.py
#install dependency
pip install -r requirement.tx
#set env
export PYTHONPATH=$PYTHONPATH:`pwd`
export LC_ALL=en_US.UTF-8
```

### start stop restart ###
```shell
python bin/solve.py start

python bin/solve.py stop

python bin/solve.py restart
```


playbook
--------------

存储命令的文本文件，solve逐行读取并执行

### 单行命令的格式 ###
* [&lt;ip&gt;]
  
  主机跳转，每个脚本的第一条命令必须为主机跳转，每个playbook文件可以有一个或多个跳转语句，在表明之后的命令都在该主机执行 。命令之后不要存在空格。

* &lt;single-line shell command&gt;
  
  单行shell命令

* PUT:&lt;file to upload&gt;:&lt;path in remote host&gt;
  
  从solve所在的主机上传文件。PUT为关键字，使用":"分隔参数。第一个参数为本地文件的全路径，第二个参数为要保存在远端主机的路径。远端路径不存在则创建。远端文件存在则判断MD5码是否一致，一致则不再上传，不一致则重命名远端文件然后重新上传。命令之后不要存在空格。

* GET:&lt;local path&gt;:&lt;file in remote host&gt;
  
  从远端主机下载文件到solve所在的主机。GET为关键字，使用":"分隔参数。第一个参数为要保存在本地的路径，第二个参数为远端主机文件的全路径。本地路径不存在则创建，本地文件已经存在则重命名然后下载。命令之后不要存在空格。

* wait
  
  wait为关键字，阻塞至所有后台运行全命令结束。默认playbook的命令逐行运行，后一行命令在前一行命令执行结束后再运行，可以使用<single-line shell command> &实现将单行命令放入后台运行，从而不必阻塞后一行命令。

* global.&lt;global_var_name&gt;=&lt;other string&gt;\`&lt;shell command&gt;`&lt;other string&gt;
  
  全局参数可以通过执行shell命令的返回值获取。即符号"="之后的字符串当成shell命令运行后的结果。

* \# &lt;comment&gt;

  
  \#开头的注释。不要在注释中包含jinja模板，即双括号包含字段如{{xxx}}

### 参数替换 ###

所有命令可以使用{{&lt;var name&gt;}}指定参数为可替换参数，参数的来源
* global参数

  使用格式为{{global.&lt;global_var_name&gt;}}

  运行时替换为global.&lt;global_var_name&gt;=&lt;other string&gt;\`&lt;shell command&gt;`&lt;other string&gt;全局参数的设置值

* session参数

  使用格式为{{session.&lt;session_var_name&gt;}}

  job中的session对应的参数

* 执行对象的属性

  如执行对象A为 {"a":"aaa","b":"bbb"}，则可以使用{{a}}，替换后为"aaa"

  如执行对象A为 {"a":"A1","b":"bbb"}，关联的对象A1为 {"a1":"a111"}，则可以使用{{a.a1}}，替换后为"a111"


demo
--------------
### 使用样例 ###
redis_send redis_log redis_job redis_config为配置文件conf/config.py中设置的redis

```
#创建连接主机 名字必须为 realhost_<ip>
#全局参数
global.my_global_test=`date +%s`abc
#使用全局参数
echo {{global.my_global_test}}
#使用session参数 session参数值在创建job时设置
echo {{session.my_session_test}}
#单行命令
mysql -u{{const.db_user}} -p{{const.db_passwd}} -h127.0.0.1 -P{{db_port}} -e"show databases"
#上传文件
PUT:/tmp/my_local_file:/tmp
PUT:{{session.local_file}}:{{session.remote_path}}
下载文件
GET:/tmp:/tmp/my_remote_file
GET:{{session.local_path}}:{{session.remote_file}}
#后台运行 可以跨多个主机后台运行，即发生主机跳转也可以
echo "111" ; sleep 15 &
echo "222" ; sleep 13 &
echo "333" ; sleep 14 &
wait
```
```
#创建job
redis_job> hmset job_dcf3e208d47011e99464000c295dd589 "target" "server_mysql_10.0.0.1" "playbook" "/tmp/myplaybook.txt" "session" "session_dcf3e208d47011e99464000c295dd589"
#设置session参数 要设置的属性由playbook使用的session参数确定
redis_config> hmset session_dcf3e208d47011e99464000c295dd589 "my_session_test" "bbbbb" "local_file" "/tmp/abc.txt"
#执行job
redis_send> rpush job_list job_dcf3e208d47011e99464000c295dd589
#查看执行结果
redis_log> hgetall log_job_dcf3e208d47011e99464000c295dd589
```
```
#通过脚本模式运行
#根据提示输入 target、playbook以及需要设置的session参数
python script/solve_exe.py
```
### job的参数说明 ###

|   参数名    | 说明 | 必须 |
| :---: | :----: | :--: |
| target | 执行对象的列表，使用","分隔 | 是 |
| playbook | 对应的playbook | 是 |
| session | 如果playbook中使用session参数，则必须设置。 | - |
| begin_line | 从第playbook的第几行开始执行。如果设置这个，必须同时设置begin_host。 | - |
| begin_host | 初始连接主机的ip。因为跳过一些playbook的行，可能导致没有主机跳转语句。 | - |

### 高级用法 ###
```
#对指定执行对象终止操作
#kill_<cluster id>;由 log_job_<job id>中确定
redis_send> set kill_<cluster id> 1
#主机连接的建立与关闭
redis_send> rpsuh conn_control "10.0.0.1" "close_10.0.0.1" "10.0.0.1@@@@63d07bf6f49c11e9befb000c295dd589"
#重新执行
#可以由原有的job重新构建，并设置begin_line与begin_host,实现断点继续运行。
#直接对主机分发命令 必须先连接主机
redis_send> rpsuh cmd_10.0.0.1 "whoami"
#分发命令时设置命令的id
redis_send> rpsuh cmd_10.0.0.1 "whoami@@@@@9d21376cd47911e99464000c295dd589"
#查看主机执行过命令列表
redis_log> lrange log_host_10.0.0.1 0 100
```

### more ###
> 可由脚本 script/solve_exe.py 直接运行
> 
> 更多playbook与使用样例详见playbook目录
> 
> 通过web服务实现可视化交互，详见[solve-frontend](https://github.com/zouzhicun/solve-frontend)的说明
