# -*- coding: utf-8 -*-

import os
import time
import sys

import paramiko
from paramiko import SSHClient
from lib.utils import my_md5
from lib.password import password


class MySSH(object):
    """
    SSH远程连接类
    shell命令执行
    上传文件
    下载文件
    """
    
    def __init__(self,host_info,*arg,**kwargs):     
        self.hostname = host_info["ip"]
        self.port     = int(host_info.get("ssh_port", 22))
        self.username = host_info.get("user", "root")
        self.password = password.decrypt(str(host_info.get("passwd","")))
        
        self.ssh_client=None
        
    def init_conn(self):
        """
        初始化连接
        """
        client = SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #默认使用运行该程序用户的ssh目录即 ~/.ssh 进行免密认证。如文件 ~/.ssh/id_rsa
        #同时也支持ssh-agent加载其他位置的私钥文件，先加载后启动该程序
        client.connect(hostname=self.hostname, port=self.port, username=self.username, password=self.password)
        self.ssh_client=client
         
    def exe_cmd(self,cmd,background_log_set=None):
        """
        执行命令
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
        
        if background_log_set:
            #使用传入的函数动态处理stdout stderr
            out,err=background_log_set(stdout, stderr)
        else:
            out=stdout.read()
            err=stderr.read()
        
        exit_code=stdout.channel.recv_exit_status()
        return out,err,exit_code
        
    def copy_file(self,exist_remote_file,remote_file,local_md5,local_filesize,is_copy_by_link=True,set_info=None,set_step=None):
        """
        复制文件，可以通过创建链接代替
        """
        def _set_step(step):
            if set_step:
                set_step(step)
        
        ftp_client=self.ssh_client.open_sftp()
        if not self.is_remote_file(ftp_client,exist_remote_file,local_md5,set_step):
            return "",local_md5,0,"remote file to copy not exist"
                
        if self.is_remote_file(ftp_client,remote_file,local_md5,set_step):
            remote_md5=local_md5
            return remote_md5,local_md5,remote_md5==local_md5,"copy same file and md5"
            
        remote_path=os.path.dirname(remote_file)
        self.remote_mkdirs(ftp_client,remote_path)    
        if is_copy_by_link:
            try:
                ftp_client.symlink(exist_remote_file,remote_file)
                remote_md5=local_md5
            except:
                #windows服务器不支持创建链接，使用复制代替
                ftp_client.putfo(ftp_client.open(exist_remote_file),remote_file,local_filesize,callback=set_info)
                _set_step("calculate remote md5 begin")
                remote_md5=self.md5_remote(ftp_client,remote_file)
                _set_step("calculate remote md5 done")
        else:
            ftp_client.putfo(ftp_client.open(exist_remote_file),remote_file,local_filesize,callback=set_info)
            _set_step("calculate remote md5 begin")
            remote_md5=self.md5_remote(ftp_client,remote_file)
            _set_step("calculate remote md5 done")
        
        return remote_md5,local_md5,remote_md5==local_md5,"copy file"
    
    def put_file(self,local_md5,local_file,remote_path,set_info=None,set_step=None):
        """
        从本地上传文件到远端 文件名不变
        远端目录如果不存在 则创建一个
        远端文件如果存在 则使用时间戳重命名远端文件
        """
        def _set_step(step):
            if set_step:
                set_step(step)
        
        if not os.path.isfile(local_file):
            return "","",0,"local file not exist"
        #_set_step("calculate local md5 begin")
        #local_md5=my_md5(file=local_file)
        #_set_step("calculate local md5 done")
        local_filesize=os.path.getsize(local_file)

        ftp_client=self.ssh_client.open_sftp()

        if self.is_remote_file(ftp_client,remote_path):
            #给的目录为文件
            return local_md5,"",0,"remote dir is a file"
        
        self.remote_mkdirs(ftp_client,remote_path)

        file_name=os.path.basename(local_file)
        remote_file=os.path.join(remote_path,file_name)
        
        if self.is_remote_file(ftp_client,remote_file,local_md5,set_step):
            remote_md5=local_md5
            msg="upload same file and md5"
        else:
            ftp_client.put(local_file,remote_file,callback=set_info)
            _set_step("calculate remote md5 begin")
            remote_md5=self.md5_remote(ftp_client,remote_file)
            _set_step("calculate remote md5 done")
            msg="upload file"
                    
        ftp_client.close()
        return local_md5,remote_md5,local_md5==remote_md5,msg
             
    def get_file(self,local_path,remote_file,set_info,set_step=None):
        """
        下载文件到本地 文件名不变
        如果本地文件存在 则使用时间戳重命名现有文件
        如果本地目录不存在 则创建
        """
        def _set_step(step):
            if set_step:
                set_step(step)
        
        ftp_client=self.ssh_client.open_sftp()
        
        if not self.is_remote_file(ftp_client,remote_file):
            return "","",0,"remote file not exist"

        file_name=os.path.basename(remote_file)
        local_file=os.path.join(local_path,file_name)

        if os.path.exists(local_file):
            os.rename(local_file,local_file+"_"+str(time.time()))
        elif not os.path.exists(local_path):
            try:
                os.makedirs(local_path)
            except:
                return "","",0,"create local dir failed"
        elif os.path.isfile(local_path):
            return "","",0,"create local dir failed,it is a file"
 
        ftp_client.get(remote_file,local_file,set_info)

        _set_step("calculate local md5 begin")
        local_md5=my_md5(file=local_file)
        _set_step("calculate local md5 done")
        _set_step("calculate remote md5 begin")
        remote_md5=self.md5_remote(ftp_client,remote_file)
        _set_step("calculate remote md5 done")
        
        ftp_client.close()
        return local_md5,remote_md5,local_md5==remote_md5,""
    
    def is_remote_file(self,ftp_client,remote_file,local_md5="",set_step=None):
        """
        判断远端文件是否存在以及md5是否一致
        """
        def _set_step(step):
            if set_step:
                set_step(step)
        
        try:
            #给的文件路径可能为目录
            ftp_client.listdir(remote_file)                #
            return False
        except:
            remote_dir,remote_filename=os.path.split(remote_file)
            try:
                if remote_filename in ftp_client.listdir(remote_dir): 
                    if not local_md5:
                        return True
                        
                    try:
                        _set_step("calculate remote md5 in check begin")
                        remote_md5 = self.md5_remote(ftp_client,remote_file)
                        _set_step("calculate remote md5 in check done")
                    except:
                        #由于文件可能是软连接 而原来的文件在已经被删除的情况下读取失败                
                        remote_md5=""
                    
                    if local_md5 == remote_md5:
                        return True
                        
                    try:
                        ftp_client.posix_rename(remote_file,remote_file+"_"+str(time.time()))
                    except:
                        ftp_client.rename(remote_file,remote_file+"_"+str(time.time()))
                    
                    return False
                    
                else:
                    return False
            except:
                return False
    
    def remote_mkdirs(self,ftp_client,remote_path):
        """
        由远端完整路径在远端创建目录
        类似 mkdir -p
        """
        if self.is_remote_file(ftp_client,remote_path):
            #给的目录为文件
            raise Exception("remote dir is a file")
        
        p=remote_path
        dir_list=[]
        while True:
            try:
                ftp_client.listdir(p)
                break
            except:
                dir_list.append(p)
                p=os.path.dirname(p)
        
        dir_list.reverse()
        
        if dir_list:
            #可能存在其他并发同时创建 只需确保最好一个创建成功即可
            try:
                for d in dir_list[:-1]:
                    ftp_client.mkdir(d)
            except:
                pass
            
            ftp_client.mkdir(dir_list[-1])
    
    def md5_remote(self,ftp_client,fullname):
        """
        计算远端的MD5
        """
        md5 = ""
        try:
            # 在远端计算MD5值，不必将文件读取到本地再计算，但有可能出现错误
            md5_raw,err,exit_code =self.exe_cmd("md5sum "+fullname)
            try:
                md5_raw=str(md5_raw,encoding="utf8")
            except:
                pass
            md5=md5_raw.split(" ")[0]
            
        except:
            from traceback import format_exc
            #向stderr输出
            sys.stderr.write(format_exc())
            exit_code=-100        
        
        if exit_code != 0:
            md5 = my_md5(afile=ftp_client.open(fullname))
        
        return md5
