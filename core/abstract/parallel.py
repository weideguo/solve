# -*- coding: utf-8 -*-
import sys
#if sys.version_info>(3,0):
#    import queue as Queue
#else:
#    import Queue
import threading
from threading import Thread
from traceback import format_exc

from lib.wrapper import logger,logger_err
from lib.compat import Queue

class AbstractThread(object):
    """
    线程并发抽象类
    第一级线程 无限循环主线程+普通线程
    第二级线程 无限循环主线程 生产多个无限循环后台线程
    第三级线程 无限循环后台线程生成实际实行的线程 这类型线程数量会比较多 因而需要线程数控制
    """
    
    def __init__(self):
        self.run_flag=True              #是否继续运行后台线程
        self.parallel_list=[]           #list的值传给get_func_args 控制无限循环后台线程数量
        self.thread_list=[]             #第一级线程列表

    
    def init_parallel(self,t_number,stop_able=True,join=False):
        self.thread_q=Queue.Queue(t_number)         #控制线程生成 
        self.b_thread_q=Queue.Queue(t_number)       #存储在运行的后台线程
        self.stop_able=stop_able                    #获取参数失败或线程运行失败是否结束无限循环
        self.join=join                              #启动所有线程后是否等待线程运行结束


    def real_func(self,*args,**kwargs):
        """单个线程的实际操作"""
        print("do something here")
        
    
    def get_func_args(self,parallel_arg):
        """返回值供real_func使用 如有返回务必为tuple类型数据"""
        print("get function args")
   
    
    def __single(self,*args):
        """单个线程的调用与控制"""
        try:
            self.real_func(*args)
        except:
            #发生线程执行异常是否退出无限循环
            self.run_flag = not self.stop_able
            logger_err.info(format_exc())
            
        self.thread_q.get(block=False) 
        #弹出已经结束的线程
        _qsize=self.b_thread_q.qsize()
        for i in range(_qsize):
            t=self.b_thread_q.get()
            if t.name==threading.current_thread().name:
                #print(t.name+" done")
                break
            self.b_thread_q.put(t)
                
    
    def __single_forever(self,parallel_arg): 
        """无限循环后台线程 控制实际执行线程的生成"""
        while self.run_flag:  
            #先线程控制阻塞避免命令队列被提前消耗
            self.thread_q.put(1)    
            #阻塞的后可能出现中断信号
            if not self.run_flag:
                break
            try:
                #获取参数可能发生阻塞
                args=self.get_func_args(parallel_arg) 
            except:
                #发生获取参数异常是否退出无限循环
                self.run_flag = not self.stop_able
                logger_err.info(format_exc())
            if not self.run_flag:
                break
            
            t=Thread(target=self.__single,args=args)
            t.start()    
            #print(t.name+" start")
            if self.b_thread_q.full():
                #不应该存在该操作 在此防止万一
                self.b_thread_q.get()
            self.b_thread_q.put(t)
                
    
    def __serve_forever(self):
        """parallel_list控制无限循环后台线程数，参数传给后台线程"""
        t_list=[]
        for parallel_arg in self.parallel_list: 
            t=Thread(target=self.__single_forever,args=(parallel_arg,))     
            t_list.append(t)
        
        for t in t_list:
            t.start()
        
        for t in t_list:
            t.join()        
            
    
    def serve_forever(self):
        """整体线程运行"""
        if self.parallel_list:
            t=Thread(target=self.__serve_forever)
            self.thread_list.append(t)
        
        for t in self.thread_list:
            t.start()
            
        if self.join:
            for t in self.thread_list:
                t.join()                       
