# coding=utf-8
import json
import os
from typing import Optional
import re


class Config:
    name = 'RemoteControl'  # 此项目名
    version = '1.0'  # 当前版本号
    originPath = '.'  # 启动路径（会变化）
    user = ('', '')  # 图片发送邮箱 SMTP 账号密码
    password = 'MyComputerAzazo1'  # 锁屏默认密码
    readRange = 32768  # 套接字一次读取长度（字节）
    longestCommand = 2 ** 15  # 最长命令长度（字节）
    socketTimeoutSec = 5  # 套接字超时时间（秒）
    longestShowTextTime = 10000  # showText命令最长显示时间（毫秒）
    authenticationTimeoutMilli = 10000  # 鉴权过期时间（毫秒）
    loopingRate = 60  # 每秒循环进行次数
    encoding = 'utf-8'  # 编码
    usingMultiprocessing = False  # 是否使用多进程（慢）
    key = "azazo1Bestbdsrjpgaihbaneprjaerg".encode(encoding)  # 传输加密密钥
    clearDeadClient = True  # 服务器是否定期删除断开连接的客户端
    processQueueMaxsize = 100  # 多进程时 Queue 最大尺寸
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
    Config.originPath = os.popen("chdir").read().rstrip()
    print('初始路径:', Config.originPath)


def readVar() -> Optional[dict]:
    try:
        with open(Config.variablesFile, 'rb') as r:
            var: dict = json.loads(r.read().decode(Config.encoding))
    except Exception:
        return None
    return var


def changeVar(changes: dict):
    var = readVar()
    if var:
        var.update(changes)
        with open(Config.variablesFile, 'wb') as w:
            w.write(json.dumps(var).encode(Config.encoding))


def clearVar(say=True):
    try:
        os.chdir(Config.originPath)
        os.remove(Config.variablesFile)
    except FileNotFoundError:
        print(Config.variablesFile, '清除失败') if say else None


def switchesParse(sys_args: list):
    """
    分析启动参数
    -F/f 强制关闭前面的实例然后启动
    """
    switches = []
    for arg in (sys_args):
        if arg.lower() == '-f':
            clearVar(False)
            switches.append(arg)
    for switch in switches:
        sys_args.remove(switch)


def hasInstance() -> bool:
    """
    查看是否有已进行的实例(请在init前调用) todo 判断进程实例
    """
    file = os.path.exists(Config.variablesFile)
    tasks = os.popen('tasklist').read().lower()
    processes = len(re.findall(r'pythonw?\.exe', tasks))
    return file and processes > 1  # 有一个是本进程
