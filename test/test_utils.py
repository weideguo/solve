#coding:utf8
from lib.utils import *


if __name__=="__main__":
      
    #hash_bytestr_iter(file_block_iter("/home/darren.wei/glibc-2.15.tar.gz"),hashlib.md5())  
       
    #hash_bytestr_iter(file_block_iter(afile=open("/home/darren.wei/glibc-2.15.tar.gz","rb")),hashlib.md5())      
    """
    print my_md5(file="/home/darren.wei/glibc-2.15.tar.gz")
    print my_md5(str="中文")
    print my_md5(afile=open("/home/darren.wei/glibc-2.15.tar.gz","rb"))
    """
    #print file_row_count('/home/darren.wei/xxx.sh')
    print get_host_ip()
