简体中文 | [English](./README.en.md)

# SOLVE ![](./solve.ico)

<!-- 暂时不展示 [![travis-ci](https://img.shields.io/travis/zouzhicun/solve.svg)](https://travis-ci.org/zouzhicun/solve) -->
[![Python 2.7|3.5|3.7](https://img.shields.io/badge/python-2.7%7C3.5%7C3.7-blue.svg)](https://github.com/zouzhicun/solve) 
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/zouzhicun/solve/blob/master/LICENSE) 


Simple command deliver server, base on SSH. 

基于SSH实现的命令分发服务, 由redis存储数据。对[执行对象(target)](#target)运行[playbook](#playbook)，即为对主机运行shell命令的扩展。


start
--------------

### dependency servers ###
* redis (>= 2.0.0)
* salt (使用salt分发时才必须, [README.salt.md](./README.salt.md))


### prerun ###
```shell
#set config
vim conf/config.conf
#install dependency
pip install -r requirements.txt
#set env
#export PYTHONPATH=$PYTHONPATH:`pwd`
export LC_ALL=en_US.UTF-8
```

### start stop restart ###
```shell
python bin/solve.py start

python bin/solve.py stop

python bin/solve.py restart
```


### usage ###
设置好[playbook](#playbook)和[执行对象](#target)之后  
* python script/solve_exe.py   #由[脚本](./script/solve_exe.py)构建[任务](#job)运行
* 通过web服务实现可视化交互，详见[solve-stack](https://github.com/zouzhicun/solve-stack)


playbook
--------------

存储命令的文本文件，solve逐行读取并执行

### 单行命令的格式 ###
* [&lt;ip&gt;]
  
  主机跳转，每个脚本的第一条命令必须为主机跳转，每个playbook文件可以有一个或多个跳转语句，在表明之后的命令都在该主机执行 。命令之后不要存在空格。

* &lt;single-line shell command&gt;
  
  单行shell命令

* wait
  
  wait为关键字，阻塞至所有后台运行全命令结束。默认playbook的命令逐行运行，后一行命令在前一行命令执行结束后再运行，可以使用<single-line shell command> &实现将单行命令放入后台运行，从而不必阻塞后一行命令。

* global.&lt;global_var_name&gt;=&lt;other string&gt;\`&lt;shell command&gt;`&lt;other string&gt;
  
  全局参数可以通过执行shell命令的返回值获取。即符号"="之后的字符串当成shell命令运行后的结果。

* select.&lt;select_var_name&gt;=&lt;other string&gt;\`&lt;shell command&gt;`&lt;other string&gt;

  与global参数使用类似，不同为其值为获取shell命令的返回值，再进行手动选择的值，用于交互执行。

* \# &lt;comment&gt;

  \#开头的注释。不要在注释中包含jinja模板，即双括号包含字段如{{xxx}}

* \_\_&lt;keyword&gt;\_\_ 自定义扩展命令
  
  开头单词以 “__” 包围的命令行被当成扩展命令自定义实现，使用格式形同普通的shell，即 cmd arg1 args ...
  
  暂时只实现 \_\_put\_\_ \_\_get\_\_ 两个命令
  
  \_\_put\_\_ &lt;file to upload&gt; &lt;path in remote host&gt; 
  
  从solve所在的主机上传文件。\_\_put\_\_为关键字，使用空格分隔参数。第一个参数为本地文件的全路径，第二个参数为要保存在远端主机的路径。远端路径不存在则创建。远端文件存在则判断MD5码是否一致，一致则不再上传，不一致则重命名远端文件然后重新上传。命令之后不要存在空格。

  \_\_get\_\_ &lt;file in remote host&gt; &lt;local path&gt;
  
  从远端主机下载文件到solve所在的主机。\_\_get\_\_为关键字，使用空格分隔参数。第一个参数为远端主机文件的全路径，第二个参数为要保存在本地的路径。本地路径不存在则创建，本地文件已经存在则重命名然后下载。命令之后不要存在空格。


### 参数替换 ###

所有命令可以使用{{&lt;var name&gt;}}指定参数为可替换参数，参数的来源
* global参数

  使用格式为{{global.&lt;global_var_name&gt;}}

  运行时替换为global.&lt;global_var_name&gt;=&lt;other string&gt;\`&lt;shell command&gt;`&lt;other string&gt;全局参数的设置值

* select参数

  与global参数使用类似

* session参数

  使用格式为{{session.&lt;session_var_name&gt;}}

  job中的session对应的参数

* 执行对象的属性

  如执行对象A为 {"a":"aaa","b":"bbb"}，则可以使用{{a}}，替换后为"aaa"

  多层级参数如{{a.a1}}，详见[执行对象](#target)的说明
  

target
--------------

hash类型的redis key。执行对象本质即为参数的集合，用于在实际执行时对playbook进行变量替换，得到实际的要执行的命令。执行对象可以通过执行对象名的引用实现多层级参数。

* 特殊执行对象 realhost_&lt;ip&gt;

  以realhost_开头的特殊执行对象存储创建ssh连接的信息。如realhost_10.0.0.1，则存储10.0.0.1的创建ssh连接的信息，playbook使用`[10.0.0.1]`命令创建ssh连接时使用该配置信息。
  
  字段说明：

  |   参数名    | 说明 | 必须 |
  | :---: | :----: | :--: |
  | ip        | 创建ssh连接用的ip                              | 是 |
  | user      | 创建ssh连接用的user，不设置则默认root          | -  |
  | ssh_port  | ssh的端口，不设置则默认22                      | -  |
  | passwd    | ssh的密码，在主机设置免密登陆时则不需要设置    | -  |
  | proxy     | 使用的代理名，对应proxy的mark，不设置则为直连  | -  |

* 普通执行对象
  
  普通的存储信息的对象
  
  如执行对象A为 {"a":"A1","b":"bbb"}，关联的对象A1为 {"a1":"a111"}，则playbook可以使用变量{{a.a1}}，替换后为"a111"


job
--------------
由[playbook](#playbook)和[执行对象](#target)可以构建成一个任务。

### job的参数说明 ###

|   参数名   | 说明 | 必须 |
| :---: | :----: | :--: |
| target     | 执行对象的列表，使用","分隔                                    | 是 |
| playbook   | 对应的playbook（绝对路径，或者参照playbook目录的相对路径）     | 是 |
| session    | 用于引入临时的参数，如果playbook中使用session参数，则必须设置  | - |
| begin_line | 从第playbook的第几行开始执行                                   | - |


demo
--------------
### 使用样例 ###
redis_send redis_log redis_job redis_config为配置文件conf/config.py中设置的redis，即conf/config.conf对应的模块

更多playbook与使用样例详见[playbook示例目录](./playbook/simple/)

```shell
#playbook命令样例
#跳转语句 左右只允许存在空格
[10.0.0.1]
[{{ip}}]
#全局参数
global.my_global_test=`date +%s`abc
#使用全局参数
echo {{global.my_global_test}}
#使用session参数 session参数值在创建job时设置
echo {{session.my_session_test}}
#单行命令
mysql -u{{const.db_user}} -p{{const.db_passwd}} -h127.0.0.1 -P{{db_port}} -e"show databases"
#上传文件 远端目录不存在则创建 文件名跟本地一样 
#通过md5判断是否一致 远端文件存但md5不一样则被重命令
__put__ /tmp/my_local_file /tmp
__put__ {{session.local_file}} {{session.remote_path}}
#上传也可以后台运行
__put__ {{session.local_file}} {{session.remote_path}} &
#下载文件 本地目录不存在则创建 文件名跟远端的一样 本地文件存在则被重命令
__get__ /tmp/my_remote_file /tmp
__get__ {{session.remote_file}} {{session.local_path}} 
#下载也可以后台运行
__get__ {{session.remote_file}} {{session.local_path}} &
#后台运行 &之后只允许存在空格
#可以跨多个主机后台运行，即发生主机跳转也可以
echo "111" ; sleep 15 &
echo "222" && sleep 13 &
echo "333" && sleep 14 &
#等待所有后台运行的结束 左右只允许存在空格
wait
```
```
#创建job
cat > /tmp/myplaybook.txt <<EOF
[{{ip}}]
echo {{ip}}
echo {{port}}
EOF

#以下操作要在redis操作
#创建连接主机 名字必须为 realhost_<ip> 格式固定
redis_config> hmset realhost_10.0.0.1 ip 10.0.0.1 user root ssh_port 22 passwd my_ssh_passwd
#默认使用运行该程序用户的ssh目录即 ~/.ssh 进行免密认证。如文件 ~/.ssh/id_rsa。如果预先进行免密登陆设置，则passwd的值设置与否或者是否正确无关紧要，优先使用免密设置。
#同时也支持ssh-agent加载其他位置的私钥文件，先加载后启动该程序
#realhost_<ip> 的passwd 可以为加密后的字符串
#python script/solve_password.py 'my_ssh_passwd'   #由原始密码生产加密字符串
#python script/solve_password.py -d '$aes_password$KzZPM01rO2wtLkcwelt6KA==$ILeCn13IoiPjE6OwpZSxLA=='  #解密验证
redis_config> hmset realhost_10.0.0.1 ip 10.0.0.1 user root ssh_port 22 passwd '$aes_password$KzZPM01rO2wtLkcwelt6KA==$ILeCn13IoiPjE6OwpZSxLA=='
#设置执行对象
redis_config> hmset server_mysql_10.0.0.1 ip 10.0.0.1 port 3306
#设置session参数 要设置的属性由playbook使用的session参数确定
redis_tmp> hmset session_dcf3e208d47011e99464000c295dd589 "my_session_test" "bbbbb" "local_file" "/tmp/abc.txt"
#创建job
redis_job> hmset job_dcf3e208d47011e99464000c295dd589 "target" "server_mysql_10.0.0.1" "playbook" "/tmp/myplaybook.txt" "session" "session_dcf3e208d47011e99464000c295dd589"
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

### 高级用法 ###
```
#对指定执行对象终止操作
#kill_<cluster id>;由 log_job_<job id>中确定
redis_send> set kill_<cluster id> 1
#设置cluster执行一条命令后阻塞，再次插入0则继续执行一条命令后阻塞
redis_send> rpush block_<cluster id> 0
#结束阻塞，剩下的命令按正常顺序全部执行
redis_send> rpush block_<cluster id> -1
#阻塞超时，剩下的命令全部不执行，不需要手动操作，通过redis的blpop实现超时
redis_send> rpush block_<cluster id> "pause timeout"
#其他值则可以结束阻塞并终止之后的所有操作
redis_send> rpush block_<cluster id> abort
#主机连接的建立与关闭
redis_send> rpush conn_control "10.0.0.1" "close_10.0.0.1" "10.0.0.1@@@@63d07bf6f49c11e9befb000c295dd589"
#重新执行
#可以由原有的job重新构建，并设置begin_line,实现断点继续运行。
#直接对主机分发命令 必须先连接主机
redis_send> rpsuh cmd_10.0.0.1 "whoami"
#分发命令时设置命令的id
redis_send> rpsuh cmd_10.0.0.1 "whoami@@@@@9d21376cd47911e99464000c295dd589"
#查看主机执行过命令列表
redis_log> lrange log_host_10.0.0.1 0 100
#session_all开头的key即为select参数的等号右边命令返回值，返回值用于在设置select参数时进行参考
redis_send>keys session_all*
#设置select参数的值，设置后才会继续运行下一行命令（只插入一个值），一个select_all对应一个select
redis_send>rpush select@@@@@a20fb0fcd6ec11eaadc7000c295dd589 "aaa bbb ccc"
```


### 锁 ###
```shell
#内部使用两种锁机制用于安全控制以及阻塞冗余操作
#查看主机的锁
python script/solve_lock.py 10.0.0.1 
#更详细的查看
python script/solve_lock.py -a 10.0.0.1
#释放锁 需要根据提示输入
python script/solve_lock.py -r 10.0.0.1 
#强制释放锁 需要根据提示输入
python script/solve_lock.py -f 10.0.0.1 
```


extend
--------------
### 系统支持 ###
* linux 启动ssh服务，同时stfp可以使用。
* windows 安装ssh，启动ssh同时stfp可以使用（建议安装如MinGW，实现类unix命令操作）。

### proxy模式 ###
proxy模式用于作为master的代理管理主机连接。整体任务协调均由master发起。 
适用于多机房模式，一个机房使用一个proxy；或者使用多个proxy减少master发起大量ssh连接的压力。  

* proxy启动方式:  
  1.命令行中 python bin/solve.py start proxy  
  2.修改配置文件conf/config.py的PROXY，即设置conf/config.conf的proxy模块
* proxy与master的通信通过redis实现  
* 默认启动的模式为master模式，不需要与其他节点有关联  
* 指定主机使用proxy管理，则格式如 realhost_proxy:10.0.0.1:192.168.16.1 ip proxy:10.0.0.1:192.168.16.1  
* porxy:&lt;proxy_mark&gt;:&lt;host_ip&gt;  
* proxy与master文件的同步尚未实现，需要额外的文件同步之后（如使用rsync），才能对proxy管理的主机执行文件上传操作  
* 主机也可以通过proxy字段设置使用的代理，但优先使用ip字段，格式如 realhost_192.168.16.1 proxy 10.0.0.1 ...

### fileserver ###
提供简单的文件管理restful接口，可以实现文件上传、下载、文件查看、目录创建，文件内容查看。  
当solve与web服务处于不同主机时，可以启用fileserver以实现文件的管理。  
conf/config的fileserver参数控制是否启用。  
不带权限验证，启用时请务必确保网络安全。（如：1.只监听本地地址/内网地址；2.防火墙+nginx+https）  

### 本地执行 ###
修改配置文件conf/config.py的local_ip_list，发往该ip列表的地址将不会使用ssh模式运行，而是直接在本地运行。  
对于proxy模式，则格式如：proxy:&lt;proxy_mark&gt;:127.0.0.1，对该主机执行时直接在proxy执行，而不是在proxy上通过ssh执行。  
127.0.0.1或proxy:&lt;proxy_mark&gt;:127.0.0.1不需要预先设置，但也可以设置以用于参数渲染（proxy字段不生效，需要设置ip字段指定是在本地或代理的本地）。    
命令缓存于队列cmd_127.0.0.1 或 cmd_proxy:&lt;proxy_mark&gt;:127.0.0.1  

### 部署架构 ###
本地执行在多master或者多proxy会导致本地执行出现问题（在不同主机执行可能结果不一样，而且如果指定使用特定master/proxy会导致playbook不能适用架构变化，如发生master/proxy退出的情况），因而在这些情况谨慎考虑是否要启动本地执行。    
master/proxy服务之间的文件同步需要额外实现。（如：1.使用rsync；2.启用fileserver，并在上传文件时同时上传所有服务；3.其他自行实现的同步策略）  

* 单master模式  
  最简单模式，所有任务管理以及、主机连接只由一个master服务管理。  

* 单master-多proxy模式  
  master用于任务管理，一个proxy对应一个独立的SSH网络。  
  master/proxy需要连接相同的redis，可以使用vpn实现处于相同内网环境。  
  
* 单master-多相同proxy模式  
  与单master-多proxy模式类似，但一个独立网络部署多个proxy（proxy主要用于主机连接，可以避免主机过多时对proxy压力过大，以及提供高可用）。  
  相同proxy由相同的proxy_mark标记。proxy不要启动本地执行。    
   
* 多master-多相同proxy模式    
  与单master-多相同proxy模式类似，但同时启动多个master（避免master压力过大，以及提供高可用）。master不要启动本地执行。    
  
* 多master模式    
  与多master-多相同proxy模式类似，但没有proxy用于连接主机，仅由master处理。master不要启动本地执行。       
  
### redis config ###  
```
#redis.conf
#可设置redis的timeout参数为一个较小值，可以回收空闲的连接（不是必须，已经实现连接复用）
timeout 172800
```
