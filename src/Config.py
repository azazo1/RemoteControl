# coding=utf-8
import json
import os
from typing import Optional
import re


class Config:
    nowIP = '127.0.0.1'  # （动态变化）服务器绑定的ip地址
    port = 2004  # 服务器绑定端口
    name = 'RemoteControl'  # 此项目名
    version = '1.0.20220208'  # 当前版本号
    originPath = '.'  # 启动路径（会变化）
    user = ('', '')  # 图片发送邮箱 SMTP 账号密码
    password = 'MyComputerAzazo1'  # 锁屏默认密码
    readRange = 524288  # 套接字一次读取长度（字节）
    longestCommand = 1048576  # 最长命令长度（字节）
    socketTimeoutSec = 5  # 套接字超时时间（秒）
    longestShowTextTime = 10000  # showText命令最长显示时间（毫秒）
    authenticationTimeoutMilli = 10000  # 鉴权过期时间（毫秒）
    loopingRate = 60  # 每秒循环进行次数
    encoding = 'utf-8'  # 编码
    usingMultiprocessing = False  # 是否使用多进程（慢）
    key = "as437pdjpa97fdsa5ytfjhzfwa".encode(encoding)  # 默认传输加密密钥（随 outerConfigFile.key 变化）
    clearDeadClient = True  # 服务器是否定期删除断开连接的客户端
    reportConnection = True  # 是否提示有新的连接建立（非Authenticate）
    processQueueMaxsize = 100  # 多进程时 Queue 最大尺寸
    fileTransportMaxSize = 524288  # 传输文件内容(原)最大大小（单个包）（字节）
    fileOperateMaxSize = 1024 * 1024 * 256  # 最大传输的文件大小（post 和 get）（总）（字节）
    networkIOInfoMaxLength = 100  # 报告接收与发送消息最长长度（超过则省略）
    variablesFile = 'vars.json'
    outerConfigFile = 'config.txt'
    initialVars = {
        "blockTaskmgr": False,
        "mouseLock": False,
        "instance": -1  # 用来告知实例PID
    }

    @property
    def socketTimeoutMilli(self) -> int:
        return self.socketTimeoutSec * 1000


def init():
    with open(Config.variablesFile, 'wb') as w:  # 创建临时变量
        data = json.dumps(
            Config.initialVars
        ).encode(Config.encoding)
        w.write(data)

    changeVar({"instance": os.getpid()})

    Config.originPath = os.getcwd()

    outerKey = readOuterConfig().get("key")
    if isinstance(outerKey, str):
        Config.key = outerKey.encode(Config.encoding)  # 读取用户设置的密码取代默认密码
    print('初始路径:', Config.originPath)
    print('版本:', Config.version)


def readOuterConfig() -> dict:
    """
    读取外部的配置
    :return json对象
    """
    if not os.path.isfile(Config.outerConfigFile):
        # 初始化外部配置
        with open(Config.outerConfigFile, "w", encoding=Config.encoding) as w:
            w.write(json.dumps({
                "key": None,
            }))
    with open(Config.outerConfigFile, "r", encoding=Config.encoding) as r:
        return json.load(r) or {}


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
    for arg in sys_args:
        if arg.lower() == '-f':
            clearVar(False)
            switches.append(arg)
    for switch in switches:
        sys_args.remove(switch)


def hasInstance() -> bool:
    """
    查看是否有已进行的实例(检查Vars文件并通过Vars文件中保存的PID查询对应进程是否还存在)(请在init前调用)
    """
    file = os.path.exists(Config.variablesFile)
    if file:
        instancePID = readVar().get("instance")
        matchedTasks = os.popen(f'tasklist /FI "PID eq {instancePID}"').read().lower()
        process = bool(re.search(r'pythonw?\.exe', matchedTasks))
        return process
    return False


def killInstance():
    """
    杀死Vars中记录的PID对应线程
    :return:
    """
    if hasInstance():
        pid = readVar().get("instance")
        os.system(f"taskkill /pid {pid} /F")
