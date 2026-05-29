简体中文 | [English](./README.en.md)

# SOLVE ![](./solve.ico)

<!-- 暂时不展示 [![travis-ci](https://img.shields.io/travis/weideguo/solve.svg)](https://travis-ci.org/weideguo/solve) -->
[![Python 3.9|3.11|3.13](https://img.shields.io/badge/python-3.9%7C3.11%7C3.13-blue.svg)](https://github.com/weideguo/solve) 
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/weideguo/solve/blob/master/LICENSE) 


Simple command deliver server, base on SSH. 

基于SSH实现的命令分发服务。  

start
--------------

### dependency ###
**server**
* redis (>= 2.0.0)

**command**
* cd tar gzip pv  
* ssh sshpass  solve服务器、要控制的服务器    
* rsync md5sum  要控制的服务器


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

### start stop ###
```shell
python bin/solve.py

kill -9 ${pid}
```


### usage ###
设置好[playbook](#playbook)和[执行对象](#target)之后  
* python script/solve_exe.py   #由[脚本](./script/solve_exe.py)构建[任务](#job)运行
* 通过web服务实现可视化交互，详见[solvestack](https://github.com/weideguo/solvestack)
