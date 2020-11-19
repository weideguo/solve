# -*- coding: utf-8 -*-
import sys
import base64


def _bytes(_str):
    """str 转成 byte"""
    if sys.version_info>(3,0):
        #python3
        _str=bytes(_str, encoding="utf8")
    
    return _str

def _str(_byte):
    """byte 转成 str"""
    if sys.version_info>(3,0):
        #python3
        _byte=_byte.decode("utf8")
    
    return _byte


class Password():
    spliter="$"
    
    def __init__(self,*arg,**kwargs):
        self.kwargs=kwargs
    
    def decrypt(self,passwd):
        """
        由传入的字符串选择对应解密函数，返回解密值，兼容未加密的
        $crypt_type$aaaaaabbbbb
        """
        
        _password = passwd.split(self.spliter)
        if len(_password)>2:
            crypt_type=_password[1]
        
            if crypt_type=="aes_password" and len(_password)==4 and (not _password[0]):
                """
                $aes_password$KzZPM01rO2wtLkcwelt6KA==$ILeCn13IoiPjE6OwpZSxLA==
                """
                from lib.aes_lib import AesCrypt
                ac = AesCrypt()
                
                #ac.iv= _bytes(_password[2]) 
                ac.iv=base64.b64decode(_bytes(_password[2])) 
                p=self.spliter.join(_password[3:])
                ac.key=_bytes(self.kwargs["aes_key"])
                
                return _str(ac.decrypt(_bytes(p)))
        
        #可能为没有加密因此返回原始值
        return passwd
        
    
    def encrypt(self,passwd,crypt_type="aes_password"):
        """
        加密密码
        """
        if crypt_type=="aes_password":
            from lib.aes_lib import AesCrypt
            ac = AesCrypt()
            
            #必须确保原始iv不存在分割符号
            #ac.iv = ac.iv.replace(_bytes(self.spliter) , _bytes("A"))
            ac.key=_bytes(self.kwargs["aes_key"])
            _password=ac.encrypt(_bytes(passwd))
            
            return self.spliter+crypt_type+self.spliter+_str(base64.b64encode(ac.iv))+self.spliter+_str(_password)
        else:
            raise Exception("crypt_type %s not support" % crypt_type)
        
        
if __name__=="__main__":
    #password=Password(aes_key="""<HeK7PJpS=oE=,yN3"5;\\E=>U2lbXL|W""")  
    from conf import config
    password=Password(aes_key=config.aes_key)
    
    en_str=password.encrypt("111")
    password.decrypt(en_str)

    
    