# coding=utf-8
import base64
import json
from typing import Union

import Crypto.Cipher.AES as AES
from Crypto.Cipher._mode_cbc import CbcMode

from src.Config import Config


class Encryptor:
    encryptor: CbcMode = None
    decryptor: CbcMode = None

    @classmethod
    def toBase64(cls, data: bytes) -> bytes:
        return base64.b64encode(data)

    @classmethod
    def fromBase64(cls, data: bytes) -> bytes:
        return base64.b64decode(data)

    @staticmethod
    def addTo16(data: bytes) -> bytes:
        # while len(data) % 16 != 0:
        #     data += b'\0'
        # return data
        BLOCK_SIZE = 16
        pad_len = BLOCK_SIZE - len(data) % BLOCK_SIZE
        return data + (bytes([0]) * pad_len)

    @staticmethod
    def adaptToJava(data: bytes) -> bytes:
        return data + b'\x10' * 16

    @classmethod
    def getEnCryptor(cls) -> Union[CbcMode]:
        return cls.encryptor

    @classmethod
    def getDeCryptor(cls) -> Union[CbcMode]:
        return cls.decryptor

    @classmethod
    def resetEnCryptor(cls):
        cls.encryptor = AES.new(cls.addTo16(Config.key), AES.MODE_ECB)

    @classmethod
    def resetDeCryptor(cls):
        cls.decryptor = AES.new(cls.addTo16(Config.key), AES.MODE_ECB)

    @classmethod
    def encrypt(cls, data: bytes) -> bytes:
        if not cls.getEnCryptor():
            cls.resetEnCryptor()  # 初始化cryptor
        encryptor = cls.getEnCryptor()
        encrypted = encryptor.encrypt(cls.adaptToJava(cls.addTo16(data)))
        return encrypted
        # return aes256.encrypt(data, Config.key.decode(Config.encoding))

    @classmethod
    def decrypt(cls, data: bytes) -> bytes:
        if not cls.getDeCryptor():
            cls.resetDeCryptor()  # 初始化cryptor
        decrypter = cls.getDeCryptor()
        decrypted = decrypter.decrypt(data)
        return decrypted.rstrip(b'\0\x10')
        # return aes256.decrypt(data, Config.key.decode(Config.encoding))

    @classmethod
    def encryptToBase64(cls, data: bytes) -> bytes:
        return cls.toBase64(cls.encrypt(data))
        # return cls.encrypt(data)

    @classmethod
    def decryptFromBase64(cls, data: bytes) -> bytes:
        return cls.decrypt(cls.fromBase64(data))


if __name__ == '__main__':
    print((a := Encryptor.encryptToBase64("{‘asdffs,,sd:''fds,<::dfsfs'Fsdfsdfs''sdf;;sdf}".encode())))
    print(Encryptor.decryptFromBase64(a).decode())

    en0 = lambda : Encryptor.encryptToBase64(json.dumps(
        {'type': 'surfWebsite', 'search': "hello", "using": "firefox"}
    ).encode(Config.encoding))
    en = en0()
    print(en)
    print(Encryptor.decryptFromBase64(en0()))
    print(Encryptor.decryptFromBase64(en))
    print(Encryptor.decryptFromBase64(en))
    print(Encryptor.decryptFromBase64(en0()))
    print(Encryptor.decryptFromBase64(en))
    print(Encryptor.decryptFromBase64(en))
