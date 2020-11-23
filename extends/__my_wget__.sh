#!/bin/sh
#
#下载文件并更改权限
#__my_wget__.sh https://url_to_get/ /path_to_save/filename
#
#命令分发时使用格式为
#__my_wget__ https://url_to_get/ /path_to_save/filename
#

url=$1
dir=`dirname $2`
filename=`basename $2`

if [ ! -d ${dir} ];then
    mkdir -p ${dir}
fi
cd ${dir} 
if [ ! -f ${filename} ];then
wget ${url} -O ${filename} 2>&1
fi
chmod 755 ${filename}

