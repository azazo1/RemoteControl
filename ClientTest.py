# coding=utf-8
import json
import pprint
import socket
import time
from hashlib import md5

from src.Config import Config
from src.Encryptor import Encryptor


def send(data: bytes, encode=True):
    sock.sendall((Encryptor.encryptToBase64(data) if encode else data) + b'\n')
    print('信息发送完毕')
    get = sock.recv(Config.readRange)
    return Encryptor.decryptFromBase64(get) if encode else get


if __name__ == '__main__':
    sock = socket.socket()
    sock.connect(('localhost', 2004))
    stamp = int(time.time() * 1000)
    verified = bool(json.loads(send(json.dumps({
        "name": Config.name,
        "version": Config.version,
        "stamp": stamp,
        "md5": md5(
            bytes(Config.name + Config.version + Config.key.decode(Config.encoding) + str(stamp),
                  Config.encoding)).hexdigest()
    }).encode(Config.encoding), False)))
    if not verified:
        print('鉴权失败')
        sock.close()
        quit()
    else:
        print('鉴权成功')

    # pprint.pprint(send(b'{"type":"test","content":"D:"}'))

    # pprint.pprint(json.loads(send(b'{"type":"dir","path":"D:/"}')))

    # pprint.pprint(send(b'{"type":"showText","content":"D:","showTime":3000}'))

    # pprint.pprint(json.loads(send(b'{"type":"getDisks"}')))

    # pprint.pprint(send(b"""{"type":"lockScreen", "maxWrongTimes":50, "password":"hello"}"""))
    # time.sleep(5)
    # pprint.pprint(send(b"""{"type":"unlockScreen"}"""))

    # pprint.pprint(send(json.dumps({'type': 'closeProgram', 'pid': 4}).encode(Config.encoding)))

    # pprint.pprint(send(json.dumps({'type': 'closeProgram', 'name': "None"}).encode(Config.encoding)))

    # pprint.pprint(send(json.dumps({'type': 'clipboard', 'action': "get"}).encode(Config.encoding)))
    # pprint.pprint(send(json.dumps({'type': 'clipboard', 'action': "set", 'content': "None"}).encode(Config.encoding)))
    # pprint.pprint(send(json.dumps({'type': 'clipboard', 'action': "clear"}).encode(Config.encoding)))

    # pprint.pprint(send(json.dumps({'type': 'memoryLook'}).encode(Config.encoding)))

    # print(send(json.dumps({'type': 'queryProcess', 'all': True}).encode(Config.encoding)).decode(Config.encoding))
    #print(send(json.dumps(
    #    {'type': 'queryProcess', 'all': False, 'pid': 38372}
    #).encode(Config.encoding)).decode(Config.encoding))
    # print(send(json.dumps(
    #     {'type': 'queryProcess', 'all': False, 'name': 'cloudmusic.exe'}
    # ).encode(Config.encoding)).decode(Config.encoding))

    # pprint.pprint(send(json.dumps(
    #     {'type': 'startFile', 'file': r"D:\CloudMusic\一丝不挂 - 陈奕迅.mp3"}
    # ).encode(Config.encoding)))

    # pprint.pprint(send(json.dumps(
    #     {'type': 'surfWebsite', 'search': "你好啊", "using": "firefox"}
    # ).encode(Config.encoding)))
    # pprint.pprint(send(json.dumps(
    #     {'type': 'surfWebsite', 'url': "www.baidu.com", "using": "firefox"}
    # ).encode(Config.encoding)))

    # pprint.pprint(send(json.dumps(
    #     {'type': 'blockTaskmgr', 'block': True}
    # ).encode(Config.encoding)))

    # pprint.pprint(send(json.dumps(
    #     {'type': 'fileDetail', 'path': r"D:\Program_Projects\Python_Projects\RemoteControl\setupPython.cmd"}
    # ).encode(Config.encoding)))
    #
    # pprint.pprint(send(json.dumps({
    #     'type': 'fileTransport',
    #     "action": "get",
    #     'path': r"D:\Program_Projects\Python_Projects\RemoteControl\setupPython.cmd",
    #     "range": [1, 1000]
    # }).encode(Config.encoding)))

    # 分段 post 测试
    # for i, single in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    #     raw = single.encode(Config.encoding)
    #     data = base64.encodebytes(raw).rstrip(b"\n")
    #     MD5 = hashlib.md5(raw).hexdigest()
    #     pprint.pprint(send(json.dumps({
    #         'type': 'fileTransport', 'path': r"D:\Temp", 'action': 'post', 'part': i,
    #         'data': data.decode(Config.encoding),
    #         'name': 'test.txt',
    #         'md5': MD5
    #     }).encode(Config.encoding)))
    # pprint.pprint(send(json.dumps({
    #     'type': 'fileTransport', 'path': r"D:\Temp\test.txt", 'action': 'merge'
    # }).encode(Config.encoding)))

    # 分段 get 测试
    """
    storePath = r"D:\Temp\get"
    target = r"D:\Temp\pics.zip"
    detail = json.loads(send(json.dumps({
        'type': 'fileDetail', 'path':target,
    }).encode(Config.encoding)))
    available = detail.get("available")
    size = detail.get("size")
    md5Code = detail.get("md5")
    parts = detail.get("parts")
    if available:
        with open(storePath, 'wb') as w:
            w.write(b"\0" * size)
            for i in range(1, parts + 1):
                part = json.loads(send(json.dumps({
                    'type': 'fileTransport', 'path': target, "action": 'get', 'part': i,
                }).encode(Config.encoding)))
                part_md5 = part.get('md5')
                part_data = part.get('data')
                part_num = part.get("part")
                start = part.get('start')
                state = part.get("state")
                if state != 1:
                    print(i, 'state failed.')
                    continue
                # state == 1 说明其他内容有效
                part_data = Encryptor.fromBase64(part_data)
                if md5(part_data).hexdigest() == part_md5:
                    w.seek(start)
                    w.write(part_data)
                    print(i, 'succeeded.')
                else:
                    print(i, 'md5 failed.')
        with open(storePath, 'rb') as r:
            data = r.read()
        if md5(data).hexdigest() == md5Code:
            print('all succeeded.')
        else:
            print('some failed.')
    else:
        print('no file.')
"""
    # 分段 get 测试
    # storePath = r"D:\Temp\get"
    # target = r"D:\Temp\pics.zip"
    # detail = json.loads(send(json.dumps({
    #     'type': 'fileDetail', 'path':target,
    # }).encode(Config.encoding)))
    # available = detail.get("available")
    # size = detail.get("size")
    # md5Code = detail.get("md5")
    # parts = detail.get("parts")
    # if available:
    #     with open(storePath, 'wb') as w:
    #         w.write(b"\0" * size)
    #         for i in range(1, parts + 1):
    #             part = json.loads(send(json.dumps({
    #                 'type': 'fileTransport', 'path': target, "action": 'get', 'part': i,
    #             }).encode(Config.encoding)))
    #             part_md5 = part.get('md5')
    #             part_data = part.get('data')
    #             part_num = part.get("part")
    #             start = part.get('start')
    #             state = part.get("state")
    #             if state != 1:
    #                 print(i, 'state failed.')
    #                 continue
    #             # state == 1 说明其他内容有效
    #             part_data = Encryptor.fromBase64(part_data)
    #             if md5(part_data).hexdigest() == part_md5:
    #                 w.seek(start)
    #                 w.write(part_data)
    #                 print(i, 'succeeded.')
    #             else:
    #                 print(i, 'md5 failed.')
    #     with open(storePath, 'rb') as r:
    #         data = r.read()
    #     if md5(data).hexdigest() == md5Code:
    #         print('all succeeded.')
    #     else:
    #         print('some failed.')
    # else:
    #     print('no file.')

    # pprint.pprint(send(json.dumps({
    #     'type': 'shutdown', "action": "restart", "delay": 1000,
    # }).encode(Config.encoding)))
    # pprint.pprint(send(json.dumps({
    #     'type': 'shutdown', "action": "cancel",
    # }).encode(Config.encoding)))

    # pprint.pprint(send(json.dumps({
    #     'type': 'inputLock', "mouse": False,
    # }).encode(Config.encoding)))

    pprint.pprint(send(json.dumps({
        'type': 'takePhoto', "action": 'photo',
    }).encode(Config.encoding)))

    # pprint.pprint(send(json.dumps({
    #     'type': 'lockScreen', "password": 'hello', "maxWrongTimes": 100
    # }).encode(Config.encoding)))

    try:
        sock.close()
    except Exception:
        pass
    input("确认退出?")
