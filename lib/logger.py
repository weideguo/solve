#!/bin/env python
# -*- coding: UTF-8 -*- 

import sys
import logging
import threading

#logger = logging.getLogger(threading.current_thread().getName())
logger = logging.getLogger("standard")
logger.setLevel(logging.DEBUG)

format = logging.Formatter("%(asctime)s - %(message)s")     # output format 
sh = logging.StreamHandler(stream=sys.stdout)               # output to standard output
sh.setFormatter(format)
logger.addHandler(sh)


logger_err = logging.getLogger("error")
logger_err.setLevel(logging.DEBUG)
sh_err = logging.StreamHandler(stream=sys.stderr)
sh_err.setFormatter(format)
logger_err.addHandler(sh_err)

"""
Python 的模块就是天然的单例模式，所以多次import不会生成多个实例化对象
"""
