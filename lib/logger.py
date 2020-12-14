#!/bin/env python
# -*- coding: utf-8 -*- 

import sys
import logging
import threading


def simple_logger(name,stream=sys.stdout,level=logging.DEBUG,format="%(asctime)s - %(message)s"):
    """获取简易的日志对象 只是线程安全"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    format = logging.Formatter(format)                      # output format 
    sh = logging.StreamHandler(stream=stream)               
    sh.setFormatter(format)
    logger.addHandler(sh)
    
    return logger

