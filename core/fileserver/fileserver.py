#!/bin/env python
#coding:utf8

import os
import sys
import time
from functools import wraps
from traceback import format_exc
from logging.config import dictConfig

from flask import Flask,jsonify,request,send_from_directory,abort,make_response
app=Flask(__name__)

"""
实现简单的文件服务管理
#查看目录的内容
#中文不要使用curl测试
curl "http://127.0.0.1:9000/file/list?path=/tmp"

#创建目录
curl "http://127.0.0.1:9000/file/create?path=/tmp/a"

#上传文件
curl "http://127.0.0.1:9000/file/?path=/tmp/a" -F "file=@abc.txt"

#查看文件的内容
curl "http://127.0.0.1:9000/file/content?file=/tmp/a/abc.txt"

#下载
curl "http://127.0.0.1:9000/file/download?file=/tmp/a/abc.txt"
"""

"""
不是直接对页面提供接口，不需要太详细的错误处理
"""
def response_decoration(func):
    @wraps(func)
    def wrapper(*args,**kwargs):
        result=""
        try:
            result=func(*args,**kwargs)
        except:
            result=jsonify({"status":-100,"msg":format_exc()})
        return result    
    return wrapper
    
origin = "*"


@app.after_request
def add_header(response):
    #跨域支持
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


@app.route("/file/",methods=["POST"])
@response_decoration
def file_upload():
    #fr=request.FILES.get("file",None)      
    file = request.files.get("file")             #curl "$url" -F "file=@/root/x.txt"  
    filename = file.filename
    path=request.args.get("path")    
    
    save_path=path
    if os.path.isfile(save_path):
        #msg="路径为文件"
        return jsonify({"status":-1,"file":save_path,"msg":"arg path should not be a file"})
    elif not os.path.exists(save_path):
        os.makedirs(save_path)

    full_path=os.path.join(save_path,filename)
    #文件存在则重命名已经存在的文件
    if os.path.isfile(full_path):
        os.rename(full_path,full_path+"_"+str(time.time())) 
    
    file.save(full_path)
    #msg="上传成功"
    return jsonify({"status":1,"file":full_path,"msg":"upload success"})


@app.route("/file/<args>",methods=["GET"])
@response_decoration
def file_manage(args):
    
    if args == "content":
        filename = request.args.get("file")
        
        content=""
        try:
            with open(filename) as f:
                content=f.read()
    
            #return content
            return jsonify({"status":1,"file":filename,"content":content})
        except:
            #return jsonify({"status":-1,"file":filename,"msg":"读取文件失败"})
            return jsonify({"status":-1,"file":filename,"msg":"open file failed"})
    
    if args == "download":
        filename = request.args.get("file")
        dir = os.path.dirname(filename)
        fname = os.path.basename(filename)
        
        if os.path.isfile(filename):
            
            return send_from_directory(dir,fname,as_attachment=True)
        else:
            #return jsonify({"status":-1,"file":filename,"msg":"路径不为文件"})
            r=jsonify({"status":-1,"file":filename,"msg":"arg file is not a file"})
            return make_response(r,404)
    
    if args == "list":
        root_path = request.args.get("path")
        files=[]
        dirs=[]
        
        if not os.path.isfile(root_path) and os.path.exists(root_path):
            for x in os.listdir(root_path):
                if os.path.isfile(os.path.join(root_path,x)):
                    files.append(x)
                else:
                    dirs.append(x)
        
            files.sort()
            dirs.sort()
            return jsonify({"status":1,"path":root_path,"files":files,"dirs":dirs})
        else:
            #return jsonify({"status":-1,"path":root_path,"msg":"路径不为目录"}) 
            return jsonify({"status":-1,"path":root_path,"msg":"arg path is not a directory"}) 
    
    if args == "create":
        create_path = request.args.get("path")
        #import chardet
        #print(chardet.detect(create_path))
        try:
            os.makedirs(create_path)
            status=1
            #msg="创建成功"
            msg="create success"
        except OSError:
            status=-1
            #msg="创建失败"
            msg="create failed"
            
        return jsonify({"status":status,"path":create_path,"msg":msg})
    
    
    abort(404)
    

@app.errorhandler(404)
def miss_404(e):
    return jsonify({"status":-404,"msg":str(e)})  

@app.errorhandler(405)
def miss_405(e):
    return jsonify({"status":-405,"msg":str(e)}) 

"""
@app.errorhandler(500)
def error(e):
    return jsonify({"status":-500,"msg":"request error"})  
"""

def start(host,port,log_path="/tmp",origin="*"): 
    # 日志设置
    log_file=os.path.join(log_path,"./fileserver.log")
    dictConfig({
        "version": 1,
        "formatters": {"default": {
            "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        }},
        "handlers": {"fileoutput": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file,
            "formatter": "default",
            "maxBytes": 1024*1024,
            "backupCount": 3
        }},
        "root": {
            "level": "INFO",
            "handlers": ["fileoutput"]
        }
    })
    
    #设置允许访问的域
    origin=origin
    #抑制启动时的终端输出 因为flask建议使用WSGI方式启动
    os.environ["WERKZEUG_RUN_MAIN"]="true"
    app.run(host,port,threaded=True)
    
    
if __name__=="__main__":
    
    start("0.0.0.0",9001)
    
