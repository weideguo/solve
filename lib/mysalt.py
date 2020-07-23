# -*- coding: utf-8 -*-
#python 2.7
#salt 2018.3.3 (Oxygen)

import os
import time
import salt.client


class MySalt(object):
    """
    对salt接口的封装
    target为minion的名字 可以使用通配符 *
    """

    def __init__(self,c_path=u"/etc/salt/master"):
        """
        c_path salt-mater的配置文件
        """
        self.local=salt.client.LocalClient(c_path=c_path)

    def ping(self,target):
        """
        验证minion是否连接 并不是ICMP ping
        """
        return self.local.cmd(target,"test.ping")
   
    def md5sum(self,target,filename):
        """
        filename minon中文件完整路径
        """
        return self.local.cmd(target,"hashutil.digest_file",[filename])
   
    def exe(self,target,cmd):
        """
        执行shell命令
        """
        return self.local.cmd(target, "cmd.run_all", [cmd])      

    def move(self,target,from_path,to_path):
        """
        文件迁移 minon中文件完整路径
        """
        self.makedirs(target,os.path.dirname(to_path))
        return self.local.cmd(target,"file.move",[from_path,to_path])

    def file_exists(self,target,filename):
        """
        文件是否存在
        """
        return self.local.cmd(target,"file.file_exists",[filename])
    
    def directory_exists(self,target,path):
        """
        目录是否存在
        """
        return self.local.cmd(target,"file.directory_exists",[path])

    def makedirs(self,target,path):
        """
        创建目录类似 mkdir -p
        """
        path = path+"/"
        return self.local.cmd(target,"file.makedirs",[path])

    def link(self,target,exist_file,link_file):
        """
        创建链接 比file.copy快 但两个的结果一样 都是复制实现
        """
        c=self.file_exists(target,exist_file)
        if not c[target]:
            msg="file to make link not exist"
            r={target:msg}
        else:
            self.makedirs(target,os.path.dirname(link_file))
            r=self.local.cmd(target,"file.link",[exist_file,link_file])
        return r
        
    def put(self,target,local_file,remote_path,file_md5="",saltenv=u"base"): 
        """
        从master推文件到minion 文件名不变
        远端目录如果不存在 则创建一个
        远端文件如果存在 则使用时间戳重命名远端文件
        """
        remote_file = os.path.join(remote_path,os.path.basename(local_file))
        remote_path = remote_path+"/"
        
        #self.local.opts['file_roots'] 上传文件由此确定根目录
        #通过软连接可以将文件的绝对路径映射到 salt-master的相对路径
        salt_file = "salt:/"+local_file
        put_base = self.local.opts["file_roots"][saltenv][0]
        put_file = put_base+local_file 
                

        fe=self.file_exists(target,remote_file)
        
        file_check=False
        #防止使用通配符时key不存在
        if (target in fe) and fe[target]:
            #文件在远端已经存在
            if self.md5sum(target,remote_file)[target] != file_md5: 
                #md5不同
                self.move(target,remote_file,remote_file+"_"+str(time.time()))
                file_check=False
            else:
                #md5相同
                file_check=True
        else:
            file_check=False
    
        if not file_check:
            #get_file(path, dest, saltenv=u'base', makedirs=False, template=None, gzip=None, **kwargs)
            r=self.local.cmd(target,"cp.get_file",[salt_file,remote_path,saltenv,1,None,9]) 
            if target in r:
                if r[target] == remote_file:
                    r["is_success"]=1      
                else:
                    r["is_success"]=0      
                    if not os.path.isfile(put_file):
                        r[target]="real local file not exist: %s" % put_file
        else:
            r={target:"file exist","is_success":1}

        return r


    def get(self,target,local_path,remote_file):
        """
        从minion拉文件到master 文件名不变
        果本地文件存在 则使用时间戳重命名现有文件
        如果本地目录不存在 则创建
        """
        #self.local.opts['file_recv'] #需要为True 在master的配置文件中设置
        #self.local.opts['cachedir'] 指定获取文件存储的路径？
        #master默认存放文件的路径 /var/cache/salt/master/minions/minion-id/files

        #需要预先设置软连接实现salt-master文件映射到主机目录        

        local_file=os.path.join(local_path,os.path.basename(remote_file))
        if os.path.exists(local_file):
            os.rename(local_file,local_file+"_"+str(time.time()))    
        
        ##push(path, keep_symlinks=False, upload_path=None, remove_source=False)
        return self.local.cmd(target,"cp.push",[remote_file,0,local_file,0])
         
