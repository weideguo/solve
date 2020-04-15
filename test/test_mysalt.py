#coding:utf8
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.mysalt import MySalt

if __name__ == "__main__":
    
    salt=MySalt()
    
    target="127.0.0.1"
    salt.ping(target)
    salt.md5sum(target,"/tmp/2020045.txt")
    salt.exe(target,"who")
