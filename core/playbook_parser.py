# -*- coding: utf-8 -*-


def simple_parser(playbook):
    """
    playbook解析成单个命令 在此每一行当成一条命令
    """
    with open(playbook,"r") as f:
        next_cmd=f.readline()
        while next_cmd:
            yield next_cmd
            next_cmd=f.readline()

def get_line_by_num(playbook,num):
    """
    获取playbook中的指定行
    """
    i = 0
    for l in simple_parser(playbook):
        i = i+1
        if i == num:
            return l
    
    return ""
