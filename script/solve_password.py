#!/bin/env python
# -*- coding: utf-8 -*-
#encrypt and decrypt for password
#
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.password import password



if __name__ == "__main__":
    
    if len(sys.argv)<2 or sys.argv[1] == '--help' or sys.argv[1] == '-h':
        print("useage:")
        print("%s [ --help | -h ] | [-d <encrypted_password>] | [<origin_password>]  " % sys.argv[0])
        exit()
        
    if len(sys.argv)==3 and sys.argv[1] == "-d":
        print(password.decrypt(sys.argv[2]))
    else:
        print(password.encrypt(sys.argv[1]))
 
