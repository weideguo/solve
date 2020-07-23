# -*- coding: utf-8 -*-
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.myssh import MySSH

if __name__ == "__main__":
    
    host_info={"ip":"127.0.0.1","ssh_port":22,"user":"root","passwd":"weideguo"}
    ssh=MySSH(host_info)
    ssh.init_conn()
    ssh.exe_cmd("who")
    
    #md5sum /tmp/20200415.txt
    local_md5="8d78617188d15c095f7470fb87bac7ec"    
    local_file="/tmp/20200415.txt"
    remote_path="/tmp/aaa"
    
    ssh.put_file(local_md5,local_file,remote_path)
    
        
    exist_remote_file="/tmp/20200415.txt"
    remote_file="/tmp/20200415.txtxx"
    local_md5="8d78617188d15c095f7470fb87bac7ec"
    local_filesize=os.path.getsize(local_file)
    is_copy_by_link=True
    
    ssh.copy_file(exist_remote_file,remote_file,local_filesize,local_md5,is_copy_by_link)
