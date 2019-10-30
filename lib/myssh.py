#coding:utf8

import os
import time
import sys

import paramiko
from paramiko import SSHClient
from lib.utils import my_md5



class MySSH(object):
    """
    SSH远程连接类
    shell命令执行
    上传文件
    下载文件
    """
    
    def __init__(self,host_info,*arg,**kwargs):
        self.host_info=host_info
        self.ssh_client=None
        
   
    def init_conn(self):
        """
        初始化连接
        """
        client = SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(hostname=self.host_info["ip"],port=int(self.host_info["ssh_port"]), username=self.host_info["user"],\
                        password=self.host_info["passwd"])

        self.ssh_client=client
         
    def exe_cmd(self,cmd):
        """
        执行命令
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd)

        out=stdout.read()
        err=stderr.read()
        exit_code=stdout.channel.recv_exit_status()
        return out,err,exit_code
        
    def copy_file(self,exist_remote_file,remote_file,set_info,local_md5,local_filesize,is_copy_by_link=True):
        """
        复制文件，可以通过创建链接代替
        """
        ftp_client=self.ssh_client.open_sftp()
        if not self.is_remote_file(ftp_client,exist_remote_file,local_md5):
            return "",local_md5,0,"remote file to copy not exist"
                
        if self.is_remote_file(ftp_client,remote_file,local_md5):
            remote_md5=local_md5
            return remote_md5,local_md5,remote_md5==local_md5,"copy same file and md5"
            
        remote_path=os.path.dirname(remote_file)
        self.remote_mkdirs(ftp_client,remote_path)    
        if is_copy_by_link:
            ftp_client.symlink(exist_remote_file,remote_file)
            remote_md5=local_md5
        else:
            ftp_client.putfo(ftp_client.open(exist_remote_file),remote_file,local_filesize,callback=set_info)
            remote_md5=self.md5_remote(ftp_client,remote_file)
        
        return remote_md5,local_md5,remote_md5==local_md5,"copy file"
    
    def put_file(self,local_file,remote_path,set_info):
        """
        从本地上传文件到远端 文件名不变
        远端目录如果不存在 则创建一个
        远端文件如果存在 则使用时间戳重命名远端文件
        """
        
        if not os.path.isfile(local_file):
            return "","",0,"local file not exist"
        
        local_md5=my_md5(file=local_file)
        local_filesize=os.path.getsize(local_file)

        ftp_client=self.ssh_client.open_sftp()

        if self.is_remote_file(ftp_client,remote_path):
            #给的目录为文件
            return local_md5,"",0,"remote dir is a file"
        
        self.remote_mkdirs(ftp_client,remote_path)

        file_name=os.path.basename(local_file)
        remote_file=os.path.join(remote_path,file_name)
        
        if self.is_remote_file(ftp_client,remote_file,local_md5):
            remote_md5=local_md5
            msg="upload same file and md5"
        else:
            ftp_client.put(local_file,remote_file,callback=set_info)
            remote_md5=self.md5_remote(ftp_client,remote_file)
            msg="upload file"
                    
        ftp_client.close()
        return local_md5,remote_md5,local_md5==remote_md5,msg
             
    def get_file(self,local_path,remote_file,set_info):
        """
        下载文件到本地 文件名不变
        如果本地文件存在 则使用时间戳重命名现有文件
        如果本地目录不存在 则创建
        """
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

        local_md5=my_md5(file=local_file)
        #remote_md5=my_md5(afile=ftp_client.open(remote_file))
        remote_md5=self.md5_remote(ftp_client,remote_file)
    
        ftp_client.close()
        return local_md5,remote_md5,local_md5==remote_md5,""
    
    def is_remote_file(self,ftp_client,remote_file,local_md5=""):
        """
        判断远端文件是否存在以及md5是否一致
        """
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
                        remote_md5 = self.md5_remote(ftp_client,remote_file)
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
            md5=md5_raw.split(" ")[0]
            #logger_err.debug("calculate in remote: %s %s %s" %(md5,err,exit_code))
        except:
            exit_code=-100        
        
        if exit_code != 0:
            md5 = my_md5(afile=ftp_client.open(fullname))
            #logger_err.debug("calculate in local: %s" %(md5))
        
        return md5
