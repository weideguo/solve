# -*- coding: utf-8 -*-
import paramiko
from paramiko import SSHClient,SSHConfig


client = SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())


hostname = ""
port     = 22
username = ""
password = ""


client.connect(hostname=hostname, port=port, username=username, password=password)
        
cmd = "echo 111"        
stdin, stdout, stderr = client.exec_command(cmd)

print( stdout.read() )
print( stderr.read() )




ftp_client = client.open_sftp()

local_file  = ""
remote_file = ""

client.put(local_file,remote_file)

