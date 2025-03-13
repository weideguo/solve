# -*- coding: utf-8 -*-
import os
import re
import socket
import hashlib
import threading

def hash_bytestr_iter(bytesiter, hasher, hex_str=True):
    for block in bytesiter:
        hasher.update(block)
    return (hasher.hexdigest() if hex_str else hasher.digest())

def file_block_iter(file=None, afile=None, blocksize=65536):
    """文件时防止出现内存不够用 分块读取"""

    if file:
        afile=open(file, "rb")
    else:
        afile=afile
            
    with afile:
        block = afile.read(blocksize)
        while len(block) > 0:
            yield block
            block = afile.read(blocksize)


def my_md5(file=None,str=None,afile=None):
    """
    file     文件全路径名
    str      字符串  unicode 或者utf8编码
    afile    open()方法打开的文件对象
    """
    hasher=hashlib.md5()
    if file:
        return hash_bytestr_iter(file_block_iter(file=file),hasher)
        
    elif afile:   
        return hash_bytestr_iter(file_block_iter(afile=afile),hasher)
        
    elif str:
        try:
            str=str.encode("utf8")
        except:
            str=str
        return hash_bytestr_iter([str],hasher)
    else:
        return None


def get_host_ip(host="8.8.8.8",port=80):
    """获取本机ip"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((host, port))
        ip = s.getsockname()[0]
    finally:
        s.close()
        
    return ip


def file_row_count(file):
    """获取文件的行数,兼容大文件"""
    rownum=0   
    try:
        with open(file, "r") as f:
            buffer = f.read(8192*1024)            
            rownum += buffer.count('\n')
    except:
        rownum=0
    
    return rownum


def cmd_split(cmd_line, arg_num=0):
    """
    按照shell的格式分割命令行
    cmd_line 原始字符串
    arg_num  参数个数，0为全部按照空格划分，n为按照空格获取n-1个参数，剩余全部为最后一个
    """
    cmd_line=cmd_line.strip()
    cmd_list=[]
    temp_str=""
    for c in cmd_line:
        if arg_num:
            if len(cmd_list)>=arg_num:
                temp_str += c
            else:
                if c != " ":
                    temp_str += c
                elif temp_str:
                    cmd_list.append(temp_str)
                    temp_str=""
                else:
                    temp_str=""                
                           
        else:
            if c != " ":
                temp_str += c
            elif temp_str:
                cmd_list.append(temp_str)
                temp_str=""
            else:
                temp_str=""
            
    if temp_str:
        cmd_list.append(temp_str)
    return cmd_list


def cmd_options_split(option_str):
    """
    将形如`-compress=1 -type=file -try=4` 处理成 {"compress":"1","type":"file","try":"4"}
    """
    options = {}
    for o in option_str.strip().split(" "):
        if o:
            if len(o.split("="))==2 and (re.match("-\w+=\w+",o) or re.match("--\w+=\w+",o)):
                o = o[1:]
                if o[1] == "-":
                    o = o[1:]
                _o = o.split("=")
                options[_o[0]] = _o[1]
            else:
                raise Exception("option format error[%s]" % o)
    
    return options
    


def is_file_in_dir(shorname,postfixs,dir):
    """指定文件夹中是否存在指定后缀的文件"""
    
    _dir = os.listdir(dir)
    for postfix in postfixs:
        if shorname+postfix in _dir:
            content=""
            with open(os.path.join(dir,shorname+postfix),"r") as f:
                content=f.read()
            return shorname+postfix,content
    return "",""


def safe_decode(input):
    """转成unicode"""
    try:
        output=input.decode("utf8")
    except:
        output=input
    return output


def Singleton(cls):
    """
    线程安全的单例模式装饰器
    @Singleton
    class A():pass
    """
    _instance_lock = threading.Lock()
    _instance = {}
        
    def _singleton(*args, **kargs):
        if cls not in _instance:
            with _instance_lock:
                #等待锁释放后，对象可能已经被其他线程创建
                if cls not in _instance:
                    _instance[cls] = cls(*args, **kargs)
        return _instance[cls]
    
    return _singleton

