#coding:utf8
#一些函数的封装
from threading import Thread

def gen_background_log_set(cmd_uuid,redis_client):
    """生成执行命令时设置日志的函数"""
    def background_log_set(stdout, stderr):
        def update_log(out,tag):
            """真实用于设置日志的后台函数"""
            #防止获取到None
            redis_client.hset(cmd_uuid,tag,"")
            while True:
                #单行读取，读取不到阻塞，但读取结束后不会阻塞
                #readline(1) read(1) 作用类似，只获取一个字符，但更新太频繁，消耗太大，在其他更高实时性场景使用
                new_log=out.readline()
                try:
                    new_log=str(new_log,encoding="utf8")
                except:
                    pass
                old_log=redis_client.hget(cmd_uuid,tag)
                redis_client.hset(cmd_uuid,tag,old_log+new_log)
                # 单行读取，每一行至少为"\n"
                if not new_log:
                    break
                
                #time.sleep(1)
        
        #需要开线程同时处理stdout stderr            
        t1=Thread(target=update_log,args=(stdout,"stdout"))
        t2=Thread(target=update_log,args=(stderr,"stderr"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        
        sout=redis_client.hget(cmd_uuid,"stdout")
        serr=redis_client.hget(cmd_uuid,"stderr")
        
        #如果线程运行失败，处理None
        if not sout:
            sout = ""
        if not serr:
            serr = ""
        return sout,serr
        
    return background_log_set

