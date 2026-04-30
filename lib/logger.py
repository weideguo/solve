#!/bin/env python
# -*- coding: utf-8 -*-

import sys
import logging
from logging import handlers


def simple_logger(
    name, stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s - %(message)s"
):
    """获取简易的日志对象 只是线程安全"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    format = logging.Formatter(format)  # output format
    sh = logging.StreamHandler(stream=stream)
    sh.setFormatter(format)
    logger.addHandler(sh)

    return logger


def timed_rotating_logger(
    name,
    filename,
    level=logging.DEBUG,
    format="%(asctime)s - %(message)s",
    when="D",
    interval=1,
    backupCount=30,
    encoding="utf-8"
):
    """按照时间分割的日志对象"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    format = logging.Formatter(format)
    handler = handlers.TimedRotatingFileHandler(
        filename=filename, when=when, interval=interval, backupCount=backupCount, encoding=encoding
    )
    handler.setFormatter(format)
    logger.addHandler(handler)

    return logger
