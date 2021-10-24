# coding=utf-8
import json
import os


class Config:
    name = 'RemoteControl'  # 此项目名
    version = '1.0'  # 当前版本号
    user = ('azazo1@qq.com', 'vwvdyusgiqkmbaei')  # 图片发送邮箱 SMTP 账号密码
    readRange = 32768  # 套接字一次读取长度（字节）
    longestCommand = 2 ** 15  # 最长命令长度（字节）
    socketTimeoutSec = 5  # 套接字超时时间（秒）
    verifyTimeoutMilli = 10000  # 鉴权过期时间（毫秒）
    loopingRate = 60  # 每秒循环进行次数
    encoding = 'utf-8'  # 编码
    key = "azazo1Bestbdsrjpgaihbaneprjaerg".encode(encoding)  # 传输加密密钥
    clearDeadClient = True  # 服务器是否定期删除断开连接的客户端
    processQueueMaxsize = 100  # 进程Queue最大传送数量
    fileTransportMaxSize = 8192  # 传输文件内容最大大小（字节）
    variablesFile = 'vars.json'
    initialVars = {
        "blockTaskmgr": False,
        "mouseLock": False,
    }

    @property
    def socketTimeoutMilli(self) -> int:
        return self.socketTimeoutSec * 1000


def init():
    with open(Config.variablesFile, 'wb') as w:
        data = json.dumps(
            Config.initialVars
        ).encode(Config.encoding)
        w.write(data)


def readVar() -> dict:
    with open(Config.variablesFile, 'rb') as r:
        var: dict = json.loads(r.read().decode(Config.encoding))
    return var


def changeVar(changes: dict):
    var = readVar()
    var.update(changes)
    with open(Config.variablesFile, 'wb') as w:
        w.write(json.dumps(var).encode(Config.encoding))


def clearVar():
    os.remove(Config.variablesFile)


def hasInstance() -> bool:
    """
    查看是否有已进行的实例(请在init前调用)
    """
    return os.path.exists(Config.variablesFile)
