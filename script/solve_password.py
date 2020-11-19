#!/bin/env python
# -*- coding: utf-8 -*-
#encrypt and decrypt for password
#
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.password import Password
from conf import config

password=Password(aes_key=config.aes_key)


if __name__ == "__main__":
    
    if len(sys.argv)<2 or (sys.argv[1]=="-d" and len(sys.argv)!=3) or (sys.argv[1]!="-d" and len(sys.argv)!=2):
        print("useage:")
        print("%s [-d <encrypted_password>] | [<origin_password>]  " % sys.argv[0])
        exit()
        
    if len(sys.argv)==3 and sys.argv[1] == "-d":
        print(password.decrypt(sys.argv[2]))
    else:
        print(password.encrypt(sys.argv[1]))
 
