solve使用salt
--------------

solve使用salt分发命令


running
--------------

### version support ###
* python 2.7
* salt 2018.3.3 (Oxygen)

### prerun ###
```shell
#安装salt-master solve必须在salt运行的主机上运行
#set config    #按照提示修改使用的命令分发模块为salt
vim conf/config.py
#install dependency
pip install -r requirement2.7_salt.tx
#set env
export PYTHONPATH=$PYTHONPATH:`pwd`
export LC_ALL=en_US.UTF-8
#通过链接设置salt的目录与主机的目录的映射
#如:
#ln -s /upload /srv/salt/upload
#ls -s /download /var/cache/salt/master/minions/${minion-id}/files/download
#不能控制主机的连接与断开，需要额外启动/关闭salt-minion
#其他情况同SSH模式一致
```
