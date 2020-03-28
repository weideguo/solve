#!/bin/env python
#coding:utf8

import os
import sys
import time

from flask import Flask,jsonify,request,send_from_directory
app=Flask(__name__)

"""
实现简单的文件服务管理
#查看目录的内容
#中文不要使用curl测试
crul "http://127.0.0.1:9000/file/list?path=/tmp"

#创建目录
curl "http://127.0.0.1:9000/file/create?path=/tmp/a"

#上传文件
curl "http://127.0.0.1:9000/file/?path=/tmp/a" -F "file=@abc.txt"

#查看文件的内容
curl "http://127.0.0.1:9000/file/content?file=/tmp/a/abc.txt"

#下载
curl "http://127.0.0.1:9000/file/download?file=/tmp/a/abc.txt"
"""

from logging.config import dictConfig


origin = '*'

@app.after_request
def add_header(response):
    #跨域支持
    response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


@app.route('/file/',methods=['POST'])
def file_upload():
    #fr=request.FILES.get('file',None)      
    file = request.files.get('file')             #curl "$url" -F "file=@/root/x.txt"  
    filename = file.filename
    path=request.args.get('path')    
    
    save_path=path
    if os.path.isfile(save_path):
        msg='路径为文件'
        status=-1
        return jsonify({'file':save_path,'msg':msg,'status':status})
    elif not os.path.exists(save_path):
        os.makedirs(save_path)

    full_path=os.path.join(save_path,filename)
    #文件存在则重命名已经存在的文件
    if os.path.isfile(full_path):
        os.rename(full_path,full_path+'_'+str(time.time())) 
    
    file.save(full_path)
    status=1
    msg="上传成功"
    return jsonify({'status':status,'file':full_path,'msg':msg})


@app.route('/file/<args>',methods=['GET'])
def file_manage(args):
    
    if args == 'content':
        filename = request.args.get('file')
        
        content=''
        try:
            with open(filename) as f:
                content=f.read()
    
            #return content
            return jsonify({'status':1,'file':filename,'content':content})
        except:
            return jsonify({'status':-1,'file':filename,'msg':'读取文件失败'})
    
    
    if args == 'download':
        filename = request.args.get('file')
        dir = os.path.dirname(filename)
        fname = os.path.basename(filename)
        
        if os.path.isfile(filename):
            
            return send_from_directory(dir,fname,as_attachment=True)
        else:
            return jsonify({'status':-1,'file':filename,'msg':'路径不为文件'})
    
    
    if args == 'list':
        root_path = request.args.get('path')
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
            return jsonify({'status':1,'path':root_path,'files':files,'dirs':dirs})
        else:
            return jsonify({'status':-1,'path':root_path,'msg':'路径不为目录'}) 
    
    
    if args == 'create':
        create_path = request.args.get('path')
        #create_path = os.path.join(file_root,'./'+create_path)
        import chardet
        print(chardet.detect(create_path))
        #return create_path
        try:
            os.makedirs(create_path)
            status=1
            msg='创建成功'
        except OSError:
            status=-1
            msg='创建失败'
        
        return jsonify({'status':status,'path':create_path,'msg':msg})
        

def start(host,port,log_path="/tmp",origin='*'): 
    # 日志设置
    log_file=os.path.join(log_path,'./fileserver.log')
    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'fileoutput': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': log_file,
            'formatter': 'default',
            'maxBytes': 1024,
            'backupCount': 3
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['fileoutput']
        }
    })
    
    #设置允许访问的域
    origin=origin
    app.run(host,port,threaded=True)
    
    
if __name__=='__main__':
    
    start('0.0.0.0',9000)
    
