测试样例
----------

```shell
#测试样例数据
#假设有台主机可以分发命令
#host1的信息
host1_ip="192.168.59.131"
host1_port="22"
host1_user="root"
host1_passwd="weideguo"
#host2的信息
host2_ip="192.168.59.132"
host2_port="22"
host2_user="root"
host2_passwd="weideguo"

#设置redis的信息 config库中
#realhost对象存储主机的信息 四个字段是创建SSH连接的必须 可以增加其他字段
hmset realhost_${host1_ip} ip ${host1_ip} user ${host1_user} ssh_port ${host1_port} passwd ${host1_passwd}
hmset realhost_${host2_ip} ip ${host2_ip} user ${host2_user} ssh_port ${host2_port} passwd ${host2_passwd}

#const对象 用于存储一些常量
#存储数据库密码的常量
hmset const123 "db_user" "root" "db_passwd" "weideguo"

#设置执行对象 使用"_"分割不同层级以便前端分割 
#host类型执行对象
hmset "host_projectX_${host1_ip}" "realhost" "realhost_${host1_ip}" 
hmset "host_projectX_${host2_ip}" "realhost" "realhost_${host2_ip}" 

#server类型执行对象
hmset server_db_${host1_ip} "host" "realhost_${host1_ip}" "db_port" 3306 const const123
hmset server_db_${host2_ip} "host" "realhost_${host2_ip}" "db_port" 3306 const const123

#cluster类型执行对象
hmset cluster1 "db1" "server_db_${host1_ip}" "db2" "server_db_${host2_ip}" "site" "mysite_0001"

```


使用脚本运行任务  
```shell
python script/solve_exe.py  #根据提示输入对应信息
```


.conf文件为对应playbook在web端的控制配置，需要配合web端使用才有效。

