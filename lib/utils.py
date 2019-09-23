#coding:utf8

import socket

import hashlib

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
        thefile = open(file, 'rb')
        while True:
            buffer = thefile.read(8192*1024)
            if not buffer:
                break
            rownum += buffer.count('\n')
        thefile.close( ) 
    except:
        rownum=0

    return rownum



