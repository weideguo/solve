简体中文 | [English](./README.en.md)

# SOLVE ![](./solve.ico)

<!-- 暂时不展示 [![travis-ci](https://img.shields.io/travis/weideguo/solve.svg)](https://travis-ci.org/weideguo/solve) -->
[![Python 3.9|3.11|3.13](https://img.shields.io/badge/python-3.9%7C3.11%7C3.13-blue.svg)](https://github.com/weideguo/solve) 
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/weideguo/solve/blob/master/LICENSE) 


Simple command deliver server, base on SSH. 

基于SSH实现的命令分发服务, 由redis存储数据。对[执行对象(target)](#target)运行[playbook](#playbook)，即为对主机运行shell命令的扩展。


start
--------------

### dependency servers ###
* redis (>= 2.0.0)


### prerun ###
```shell
#set config
cp conf/config.conf.sample conf/config.conf
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
* 通过web服务实现可视化交互，详见[solvestack](https://github.com/weideguo/solvestack)


playbook
--------------

存储命令的文本文件，solve逐行读取并执行

### 单行命令的格式 ###
* `[<ip>]`
  
  主机跳转，每个脚本的第一条命令必须为主机跳转，每个playbook文件可以有一个或多个跳转语句，在表明之后的命令都在该主机执行 。命令之后不要存在空格。

* `<single-line shell command>`
  
  单行shell命令

* wait
  
  wait为关键字，阻塞至所有后台运行全命令结束。默认playbook的命令逐行运行，后一行命令在前一行命令执行结束后再运行，可以使用`<single-line shell command> &`实现将单行命令放入后台运行，从而不必阻塞后一行命令。默认在playbook的最后执行一次wait，以确保后台命令执行结束，因而最后的wait可以省略。

* ``global.<global_var_name>=<other string>`<shell command>`<other string>``
  
  全局参数可以通过执行shell命令的返回值获取。即符号“=”之后的字符串当成shell命令运行后的结果。如`$(shell command)`也是一样支持。

* ``select.<select_var_name>=<other string>`<shell command>`<other string>``

  与global参数使用类似，不同为其值为获取shell命令的返回值，再进行手动选择的值，用于交互执行。

* `# <comment>`

  \#开头的注释。不要在注释中包含jinja模板，即双括号包含字段如{{xxx}}

* `__<keyword>__`自定义扩展命令
  
  开头单词以 “__” 包围的命令行被当成扩展命令自定义实现，使用格式形同普通的shell，即 cmd arg1 args ...
  
  实现以下命令
  
  `__put__ <file to upload> <path in remote host>`
  
  从solve所在的主机上传文件。`__put__`为关键字，使用空格分隔参数。第一个参数为本地文件的全路径，第二个参数为要保存在远端主机的路径。远端路径不存在则创建。远端文件存在则判断MD5码是否一致，一致则不再上传，不一致则重命名远端文件然后重新上传。命令之后不要存在空格。

  `__get__ <file in remote host> <local path>`
  
  从远端主机下载文件到solve所在的主机。`__get__`为关键字，使用空格分隔参数。第一个参数为远端主机文件的全路径，第二个参数为要保存在本地的路径。本地路径不存在则创建，本地文件已经存在则重命名然后下载。命令之后不要存在空格。

  文件的上传、下载需要使用md5值对比，远端主机存在`md5sum`命令可以加快运行速度，不存在则使用python的代码计算且需要从远端读文件到本地因而效率不高。

  `__save__ <full filename> <file content>`
  
  可以将复杂的字符串保存到远端或本地的文件中，如字符串中包含单引号、双引号、空格、换行、`$`等特殊字符。无需任何转义，换行符需要通过参数引入，如session参数引入。

  `__sync__ <from ip_tag>:<from full path> <to path> <options>`  或 `__sync__ <from full path> <to ip_tag>:<to path> <options>` 

  内置文件、目录复制方法。不支持后台运行。<from ip_tag>与<to ip_tag>相同时只判断目录是否相同。  
  options  

  | option   | 描述                                               | 支持try类型 | 值格式               | 默认值 |
  | -------- | -------------------------------------------------- | ----------- | -------------------- | ------ |
  | try      | 进行传输的方法顺序，上一个失败则使用下一个方法传输 | -           | 1234组合             | 1234   |
  | compress | 传输时是否压缩                                     | 1,2,3       | 1 是 0 否            | 是     |
  | bwlimit  | 带宽限制                                           | 1,2,3       | 数字+k/m/g           | 空     |
  | partial  | 是否断点续传                                       | 1,2,4       | 1 是 0 否            | 是     |
  | check    | 传输结果校验，为文件则校验md5，为目录则校验大小    | 1,2,3,4     | 1 是 0 否            | 否     |
  | progress | stdout中是否显示进度                               | 1,2,3       | 1 是 0 否            | 是     |
  | proxy    | 是否其他使用代理                                   | 3           | 对应realhost的主机名 | 空     |
  | batch    | 每次从源端读取多少字节                             | 4           | 数字                 | 524288 |

  try类型说明    
  * 1 在当前执行命令的主机运行rsync。  
  * 2 在交互的另外一台主机执行命令的主机运行rsync。  
  * 3 使用代理执行ssh+管道执行数据传输，默认为solve运行的主机，可以通过proxy使用其他主机作为代理。  
  * 4 使用python的内置方法通过solve运行的主机代理传输。只支持文件，日志带有已经传输的数据量大小。    

   样例  
   ` __sync__ /a/b/c 10.0.0.1:/a/b  -compress=1 -try=1234 -proxy=192.168.0.1 -bwlimit=10m -partial=1 -check=1 --progress=1`  将目录或文件/a/b/c传输到10.0.0.1:/a/b下，目录或文件名保持原来的名字  

  其他扩展命令
  
  其他的扩展命令对应扩展目录extends下的文件，可用于自定义封装轻量级shell命令集合同时无需先预先上传文件（比较复杂的shell脚本建议上传后运行）。如 `__abc__`则类似于使用文件 `__abc__`或 `__abc__.sh` 执行。

### 参数替换 ###

所有命令可以使用`{{<var name>}}`指定参数为可替换参数，参数的来源
* global参数

  使用格式为`{{global.<global_var_name>}}`

  运行时替换为``global.<global_var_name>=<other string>`<shell command>`<other string>``全局参数的设置值

* select参数

  与global参数使用类似

* session参数

  使用格式为`{{session.<session_var_name>;}}`

  job中的session对应的参数

* 执行对象的属性

  如执行对象A为 `{"a":"aaa","b":"bbb"}`，则可以使用`{{a}}`，替换后为`"aaa"`

  多层级参数如`{{a.a1}}`，详见[执行对象](#target)的说明
  

target
--------------

hash类型的redis key。执行对象本质即为参数的集合，用于在实际执行时对playbook进行变量替换，得到实际的要执行的命令。执行对象可以通过执行对象名的引用实现多层级参数。

* 特殊执行对象 `realhost_<ip>` `realhost_<ip>_<tag>`

  以realhost_开头的特殊执行对象存储创建ssh连接的信息。如realhost_10.0.0.1，则存储10.0.0.1的创建ssh连接的信息，playbook使用`[10.0.0.1]`命令创建ssh连接时使用该配置信息。
  带有tag主要用于标记同一ip不同配置，可以为任意值，如 realhost_10.0.0.1_xxx，playbook使用`[10.0.0.1_xxx]`命令创建ssh连接。
  
  字段说明：

  |   参数名    | 说明 | 必须 |
  | :---: | :----: | :--: |
  | ip        | 创建ssh连接用的ip，也可以为ip_tag（需要与key的名字一致）                 | 是 |
  | user      | 创建ssh连接用的user，不设置则默认root                                    | -  |
  | ssh_port  | ssh的端口，不设置则默认22                                                | -  |
  | passwd    | ssh的密码，在主机设置免密登陆时则不需要设置                              | -  |
  | proxy     | solve的代理，不是ssh代理。使用的代理名，对应proxy的mark，不设置则为直连  | -  |

  免密登陆：默认加载 ~/.ssh/ 下的 id_rsa 或 id_dsa 或 id_ecdsa
  
  SSH代理： 默认使用文件 ~/.ssh/config 的代理设置，Host需要对应ip（不是ip_tag），只需要ProxyCommand模块的设置。支持设置多级代理（如 hostA->hostB->hostC->hostD，只需要在hostA的配置文件设置）。代理机必须设置免密连接。（需要设置加载 ~/.ssh/ 下的文件 id_rsa 或 id_dsa 或 id_ecdsa ）

* 普通执行对象
  
  普通的存储信息的对象
  
  如执行对象A为 `{"a":"A1","b":"bbb"}`，关联的对象A1为 `{"a1":"a111"}`，则playbook可以使用变量`{{a.a1}}`，替换后为`"a111"`


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
#通过md5判断是否一致 远端文件存但md5不一样则被重命名（加时间戳后缀）
__put__ /tmp/my_local_file /tmp
__put__ {{session.local_file}} {{session.remote_path}}
#上传也可以后台运行
__put__ {{session.local_file}} {{session.remote_path}} &
#下载文件 本地目录不存在则创建 文件名跟远端的一样 本地文件存在则被重命名（加时间戳后缀）
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
#分发的命令需要后台运行时，则需要在尾部多加一个&
#一个&为命令分发系统使用，另外一个&为实际执行时使用
#这种返回之只是一个虚构的值，需要再次确认是否运行正确，如检查进程是否存在，因而其他命令不应该依赖该命令的执行结果。
cd /data/redis && bin/redis-server redis.conf & &
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
```shell
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
#内部使用两种锁机制用于安全控制（防止启动远程连接时执行错误的过期命令）以及阻塞冗余操作（对同一主机上传多次相同文件通过复制代替）
#特殊情况下需要手动释放锁（启动远程连接时提示命令存在、上传文件时出现异常的长时等待）
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
* 主机通过proxy字段设置使用的代理，格式如 realhost_192.168.16.1 ip 192.168.16.1 proxy aaa ...
* proxy与master文件的同步尚未实现，需要额外的文件同步之后（如使用rsync），才能对proxy管理的主机执行文件上传操作  

### fileserver ###
提供简单的文件管理restful接口，可以实现文件上传、下载、文件查看、目录创建，文件内容查看。  
当solve与web服务处于不同主机时，可以启用fileserver以实现文件的管理。  
conf/config的fileserver参数控制是否启用。  
不带权限验证，启用时请务必确保网络安全。（如：1.只监听本地地址/内网地址；2.防火墙+nginx+https）  

### 本地执行 ###
修改配置文件conf/config.py的local_ip_list，发往该ip列表的地址将不会使用ssh模式运行，而是直接在本地运行。  
对于proxy模式，需要设置local_ip_list与master不相同，防止与master发生冲突。  
命令缓存于队列如：cmd_127.0.0.1 cmd_127.0.0.1_xxx

### 部署架构 ###
本地执行在多master或者多proxy，需要设置local_ip_list不同防止本地执行混乱。    
master/proxy服务之间的文件同步需要额外实现。（如：1.使用rsync；2.启用fileserver，并在上传文件时同时上传所有服务；3.其他自行实现的同步策略）  

* 单master模式  
  最简单模式，所有任务管理以及、主机连接只由一个master服务管理。  

* 单master-多proxy模式  
  master用于任务管理，一个proxy对应一个独立的SSH网络。  
  master/proxy需要连接相同的redis，可以使用vpn实现处于相同内网环境。  
  
* 单master-多相同proxy模式  
  与单master-多proxy模式类似，但一个独立网络部署多个proxy（proxy主要用于主机连接，可以避免主机过多时对proxy压力过大，以及提供高可用）。  
  相同proxy由相同的proxy_mark标记。    
   
* 多master-多相同proxy模式    
  与单master-多相同proxy模式类似，但同时启动多个master（避免master压力过大，以及提供高可用）。    
  
* 多master模式    
  与多master-多相同proxy模式类似，但没有proxy用于连接主机，仅由master处理。       

### 危险命令过滤 ###
在配置文件conf/config.py修改参数deny_commands实现对指定命令特殊处理，从而实现过滤危险命令。  
  
### redis config ###  
```
#redis.conf
#可设置redis的timeout参数为一个较小值，可以回收空闲的连接（不是必须，已经实现连接复用）
timeout 172800
```
