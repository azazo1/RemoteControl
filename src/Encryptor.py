# coding=utf-8
import base64
from typing import Union

import Crypto.Cipher.AES as AES
from Crypto.Cipher._mode_cbc import CbcMode

from src.Config import Config


class Encryptor:
    cryptor: CbcMode = None
    encoding: str = Config.encoding
    # noinspection SpellCheckingInspection
    key: bytes = Config.key
    iv = "1234567890123456"

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
    def getCryptor(cls) -> Union[CbcMode]:
        return cls.cryptor

    @classmethod
    def resetCryptor(cls):
        cls.cryptor = AES.new(cls.addTo16(cls.key), AES.MODE_CBC, cls.iv.encode(Config.encoding))

    @classmethod
    def encrypt(cls, data: bytes) -> bytes:
        if not cls.cryptor:
            cls.resetCryptor()  # 初始化cryptor
        encryptor = cls.getCryptor()
        encrypted = encryptor.encrypt(cls.adaptToJava(cls.addTo16(data)))
        return encrypted

    @classmethod
    def decrypt(cls, data: bytes) -> bytes:
        if not cls.cryptor:
            cls.resetCryptor()  # 初始化cryptor
        decrypter = cls.getCryptor()
        decrypted = decrypter.decrypt(data)
        return decrypted.rstrip(b'\0\x10')

    @classmethod
    def encryptToBase64(cls, data: bytes) -> bytes:
        return cls.toBase64(cls.encrypt(data))

    @classmethod
    def decryptFromBase64(cls, data: bytes) -> bytes:
        return cls.decrypt(cls.fromBase64(data))


if __name__ == '__main__':
    print(Encryptor.decryptFromBase64(Encryptor.encryptToBase64(b"Hi")))
