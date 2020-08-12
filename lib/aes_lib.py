# -*- coding: utf-8 -*- 
import base64
import random
from Crypto.Cipher import AES

class AesCrypt(object):
    """
    AES 加密/解密
    """
    def __init__(self):
        self.iv=self.get_key(16)
        self.key=self.get_key()
        self.mode=AES.MODE_CBC

    @staticmethod
    def get_key(key_len=32,begin_char=33,end_char=126):
        """
        key_len 16 24 32
        生产随机key
        默认只用ascii的指定字符以实现可读
        """
        return ("".join(map(lambda i : chr(random.randint(begin_char,end_char)) ,range(key_len)))).encode('latin1') 


    def encrypt(self,data):  
        """
        加密
        传入byte格式
        """
        BS = AES.block_size
        pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS).encode('latin1')    #在尾部补上字符指定补的长度
        if self.mode==AES.MODE_ECB:
            cipher = AES.new(self.key, self.mode)
        else:
            cipher = AES.new(self.key, self.mode, self.iv)
        encrypted = cipher.encrypt(pad(data))  #aes加密
        result = base64.b64encode(encrypted)   #base64 encode
        return result


    def decrypt(self,en_data):
        """
        解密
        返回byte格式
        """
        #通过最后一个字符确定补的长度，截取获取原字符串
        def unpad(s):
            try:
                return s[0:-ord(s[-1])] 
            except:
                return s[0:-s[-1]]
        if self.mode==AES.MODE_ECB:
            cipher = AES.new(self.key, self.mode)
        else:
            cipher = AES.new(self.key, self.mode, self.iv)
        result2 = base64.b64decode(en_data)
        decrypted = unpad(cipher.decrypt(result2))
        return  decrypted
        
        
    @staticmethod
    def is_valid(key,iv):
        """
        验证给的key iv是否有效
        """
        if len(iv) !=16 or (len(key) not in [16,24,32]):
            return False
        else:
            return True



if __name__ == "__main__":
    data=b"xxx"
    ac=AesCrypt()
    ac.mode=AES.MODE_ECB
    en_data=ac.encrypt(data)
    print(en_data)
    
    ac.decrypt(en_data)

if __name__ == "__main__":
    data=b"xxx"
    ac=AesCrypt()
    """
    ac.key=
    ac.iv=
    """
    print(ac.key, ac.iv)
    en_data=ac.encrypt(data)
    print(en_data)
    ac.decrypt(en_data)

    
