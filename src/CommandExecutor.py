# coding=utf-8
import io
import json
import multiprocessing
import os
import os.path as osPath
import re
import sys
import threading
import time
from threading import Thread
import tkinter as tk
import urllib.parse as upa
import webbrowser
from hashlib import md5 as MD5
from json import JSONDecodeError
from typing import Dict, Callable, List, Tuple, Union
import traceback
import psutil
import pynput.keyboard
import pyperclip

from src.Config import Config, changeVar, readVar
from src.Encryptor import Encryptor
from src.PictureSend import PictureSender


def searchLockScreenDirPath():
    for path, dirs, files in os.walk('.'):
        if 'LockScreen' in dirs:
            return osPath.join(path, 'LockScreen')
    return None


def firstRun(args: List[str]):
    for arg in args:
        Executor.subProcessExec(arg) if Config.usingMultiprocessing else Executor.threadExec(arg)


class FileTransportHelper:
    @classmethod
    def checkRange(cls, rangeObj) -> bool:
        """
        检查范围是否有效
        :param rangeObj: 从 JSON 对象中取得的原 range
        :return: 是否有效(bool)
        """
        if len(rangeObj) > 1:  # 检查 rangeObj 是否有两个元素
            left, right = rangeObj
        else:
            return False

        if not (isinstance(left, int) and isinstance(right, int)):  # 检查 left 和 right 是否有效--是否为数字
            return False

        if right - left > Config.fileTransportMaxSize or left > right or right < 1 or left < 1:  # 检查 left 和 right 是否有效--是否过大，所处范围是否有效
            return False

        return True

    @classmethod
    def getTotalPart(cls, fileSize: int):
        return (fileSize // Config.fileTransportMaxSize) + int(bool(fileSize % Config.fileTransportMaxSize))

    @classmethod
    def checkPartRange(cls, partObj, fileSize: int) -> bool:
        """
        检查分块序号是否有效
        :param partObj: 从 JSON 对象中取得的原 part
        :param fileSize: 目标文件的大小
        :return: 是否有效(bool)
        """

        if not (isinstance(partObj, int)):  # 检查 part 是否有效--是否为数字
            return False
        if 0 < partObj <= cls.getTotalPart(fileSize):
            return True
        return False

    @classmethod
    def checkFileSize(cls, fileSize: int) -> bool:
        """
        检查文件总内容大小是否符合要求
        :return True: 符合要求
                False: 不符合要求
        """
        return fileSize < Config.fileOperateMaxSize

    @classmethod
    def getPartRange(cls, part: int) -> Tuple[int, int]:
        """
        获取分块对应字节范围
        :param part: 分块序号
        :return: 范围(起始位置, 读取长度) 从零开始
        """
        start = Config.fileTransportMaxSize * (part - 1)
        return start, Config.fileTransportMaxSize

    @classmethod
    def checkParts(cls, prefix: str, name: str) -> int:
        """
        检查post时part是否齐全
        :param prefix: 路径（不含文件名）
        :param name: 文件名（不用.part）
        :return: 0为不完全，正整数为总部分数量
        """
        files = os.listdir(prefix)
        parts = list(filter(lambda a: f"{name}.part" in a, files))
        length = len(parts)
        get = [False] * length
        for i in range(len(parts)):
            if osPath.exists(osPath.join(prefix, name + f".part{i}")):
                get[i] = True
        if all(get):
            return length
        else:
            return 0


class MyProcess(multiprocessing.Process):
    def __init__(self, queue: multiprocessing.Queue, *args, **kwargs):
        super(MyProcess, self).__init__(*args, **kwargs)
        self.queue = queue


class MyThreadQueue(list):
    def __init__(self):
        super().__init__()
        self.lock = threading.Event()

    def put(self, obj):
        self.append(obj)
        self.notify()

    def get(self):
        return self.pop(0)

    def wait(self):
        try:
            self.lock.wait(10)
        except Exception:
            pass

    def notify(self):
        self.lock.set()


class ProcessInfo:
    def __init__(self, name: str, pid: int, sessionName: str, memoryUsage: int):
        """
        :param name: 映像名称
        :param pid: 进程 process id
        :param sessionName: 会话名称
        :param memoryUsage: 内存使用(KB)
        """
        self.name = name
        self.pid = pid
        self.sessionName = sessionName
        self.memoryUsage = memoryUsage

    def toTuple(self):
        return self.name, self.pid, self.sessionName, self.memoryUsage

    def __str__(self):
        return f"ProcessInfo<name={self.name}, pid={self.pid}, " \
               f"sessionName={self.sessionName}, memoryUsage={self.memoryUsage}>"


class ProcessQueryHelper:
    @classmethod
    def analyze(cls, content: str) -> list:
        results = []
        for matched in re.finditer(r"([\S ]+)\s+(\d+)\s+(\w+)\s+\d+\s+([\d,]+)", content):
            results.append(ProcessInfo(
                name=matched.group(1).strip(),
                pid=int(matched.group(2)),
                sessionName=matched.group(3),
                memoryUsage=int(matched.group(4).replace(",", ""))
            ))
        return results


class Executor:
    class CommandAnalyser:
        """解析json格式的命令"""
        _jsonDecoder = json.JSONDecoder()
        _jsonEncoder = json.JSONEncoder()

        @classmethod
        def getCommandType(cls, commandObj) -> str:
            return commandObj.get('type')

        @classmethod
        def getObj(cls, command: str):
            return cls._jsonDecoder.decode(command)

    _functionMap: Dict[str, Callable[[Dict[str, str], multiprocessing.Queue], Union[int, str, Union[str, int]]]] = None
    _analyser = CommandAnalyser()
    processes: List[multiprocessing.Process] = []
    threads: List[Thread] = []
    _lockScreenPath = None

    @classmethod
    def getLockScreenPath(cls):
        if not cls._lockScreenPath:
            cls._lockScreenPath = searchLockScreenDirPath()
            print("LockScreen 组件加载成功:", osPath.realpath(cls._lockScreenPath), file=Config.output)
        return cls._lockScreenPath

    @classmethod
    def clearProcesses(cls):
        cleared = []
        for p in cls.processes:
            if p.exitcode is not None:
                cleared.append(p)
        for p in cleared:
            cls.processes.remove(p)

    @classmethod
    def exec(cls, command: str, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        :param queue: 任务执行返回信息
        :param command:
        :return: 执行命令，返回执行信息码 -1:找不到对应命令type
        """
        if not command:
            queue.put(-1) if queue is not None else None
            return -1
        functionMap = cls.getFunctionMap()
        try:
            cmdObj: Dict = cls._analyser.getObj(command)
            func = functionMap.get(cls._analyser.getCommandType(cmdObj))
        except (JSONDecodeError, AttributeError):
            print('无效命令:', command, file=Config.output)
            queue.put(-1) if queue is not None else None
            return -1
        if func:
            return func(cmdObj, queue)
        else:
            print('无效命令:', command, file=Config.output)
            queue.put(-1) if queue is not None else None
            return -1

    @classmethod
    def subProcessExec(cls, command: str) -> Tuple[MyProcess, multiprocessing.Queue]:
        cls.clearProcesses()
        queue = multiprocessing.Queue(Config.processQueueMaxsize)
        process = MyProcess(queue=queue, target=cls.exec, args=(command, queue), daemon=True)
        cls.processes.append(process)
        process.start()
        return process, queue

    @classmethod
    def threadExec(cls, command: str) -> Tuple[Thread, List]:
        cls.clearProcesses()
        queue = MyThreadQueue()
        thread = Thread(target=cls.exec, args=(command, queue), daemon=True)
        cls.threads.append(thread)
        thread.start()
        return thread, queue

    @classmethod
    def closeProcesses(cls, wait=True):
        for process in cls.processes:
            process.join() if wait else process.terminate()

    @classmethod
    def test(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        测试
        :param cmdObj: content:需要输出的文字
        :return: 1:输出成功, 0:输出失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        content = cmdObj.get('content')
        if content:
            print(content, file=Config.output)
            result = 1
        else:
            result = 0
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def dir(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        查询指定目录下文件
        :param cmdObj: path:需要查询的目录
        :param queue:   返回一个JSON列表:
                            [
                                ['文件或文件夹名(str)', 是否是文件夹(bool), 文件大小(int, 文件夹统一为 -1)],
                                ['文件或文件夹名(str)', 是否是文件夹(bool), 文件大小(int, 文件夹统一为 -1)],
                                ...
                            ]
                        若失败则返回 0
        :return: 1:成功 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        path: str = cmdObj.get('path')
        if path and osPath.isdir(path):
            son = os.listdir(path)
            for i, single in enumerate(son):
                absPath = osPath.join(path, single)
                isDir = osPath.isdir(absPath)
                size = -1 if isDir else osPath.getsize(absPath)
                son[i] = (single, isDir, size)
            outcome = json.dumps(son)
            result = 1
        else:
            outcome = 0
            result = 0
        queue.put(outcome) if queue is not None else None
        return result

    @classmethod
    def showText(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        显示一段文字在屏幕上
        :param cmdObj:  content:被显示文字(str),
                        showTime:显示持续时间(int, 毫秒， 默认为 2000 毫秒),
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        content = cmdObj.get("content")
        showTime = cmdObj.get('showTime') or 2000
        if content and showTime and showTime <= Config.longestShowTextTime:
            showTime = int(showTime)
            root = tk.Tk()
            root.attributes('-topmost', True)
            root.attributes('-fullscreen', True)
            frame = tk.Frame(root)
            tk.Frame(frame, height=50).pack(side=tk.TOP)  # 顶部空白
            tk.Frame(frame, width=50).pack(side=tk.LEFT)  # 左部空白
            tk.Frame(frame, width=50).pack(side=tk.RIGHT)  # 右部空白
            text = tk.Text(frame)
            text.insert(0.0, content)
            text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            tk.Frame(frame, height=50).pack(side=tk.BOTTOM)  # 下部空白
            closeButton = tk.Button(frame, text='关闭', command=lambda *a: root.destroy())
            closeButton.pack(side=tk.BOTTOM)
            copyButton = tk.Button(frame, text='复制', command=lambda *a: pyperclip.copy(content))
            copyButton.pack(side=tk.BOTTOM)
            frame.place(x=0, y=0, relheight=1, relwidth=1)
            root.update()
            startTime = time.time()
            queue.put(1) if queue is not None else None  # 提前报告让客户端不再等待
            root.attributes('-topmost', False)
            try:
                while startTime + showTime / 1000 >= time.time():
                    root.update()
                root.destroy()
            except Exception:
                pass
            result = 1
        else:
            result = 0
            queue.put(result) if queue is not None else None
        return result

    @classmethod
    def getDisks(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        获取电脑上所有硬盘盘符
        :param cmdObj: nothing
        :param queue: 盘符JSON列表
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        disks = []
        for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if osPath.exists(char + ":"):
                disks.append(char + ":")
        result = 1
        queue.put(json.dumps(disks)) if queue is not None else None
        return result

    @classmethod
    def lockScreen(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        使用LockScreen锁定电脑屏幕
        :param cmdObj: maxWrongTimes:密码最多错误次数(int), password:密码(str)
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        maxWrongTimes = cmdObj.get('maxWrongTimes') or 5
        password: str = cmdObj.get('password') or Config.password
        if maxWrongTimes and password:
            configureFile = 'PasswordConfiguration.azo'
            con = {
                "KillTaskManager": False,  # 杀死任务管理器
                "FullScreen": True,  # 全屏
                "TopMost": True,  # 最高级
                "Closable": False,  # 可关闭
                "PicturePaths": ('.',),  # 末尾显示图片文件位置
                "PictureName": "azazo1_logo.png",  # 末尾显示图片文件
                "PasswordFilePath": '{}:\\Azazo1Keys\\OpeningPassword.key',  # 密码文件位置
                "EncryptedPassword": MD5(password.encode(Config.encoding)).hexdigest(),  # md5加密后的密码
                "MaximumWrongTimes": maxWrongTimes,  # 最多错误次数
                "CachePath": 'cache',  # 缓存位置
                "DeleteCache": True,  # 删除缓存
                "Restart": True,  # 失焦追踪
            }
            conPath = osPath.join(cls.getLockScreenPath(), configureFile)
            with open(conPath, 'w') as w:
                json.dump(con, w)
            result = 1
            queue.put(result) if queue is not None else None
            os.system(
                f'cd {cls.getLockScreenPath()}&&start "{sys.executable}" "LockScreen.pyw" {Config.nowIP}:{Config.port}')  # 启动锁屏
        else:
            result = 0
            queue.put(result) if queue is not None else None
        return result

    @classmethod
    def unlockScreen(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        解锁屏幕
        :param cmdObj: nothing
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        try:
            lsp = cls.getLockScreenPath()
            from src.LockScreen.LockScreen import LoginManager
            os.chdir(lsp)
            LoginManager.flushLoginSituation(True)
            os.chdir(Config.originPath)
            result = 1
        except Exception:
            traceback.print_exc(Config.errOutput)
            result = 0
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def closeProgram(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        关闭指定程序，通过程序名称或pid
        :param cmdObj:  pid:指定进程pid(int), name:指定进程名称(str)
                        name 和 pid 不需要同时提供，若同时提供了，pid优先
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        pid = cmdObj.get('pid')
        name = cmdObj.get('name')
        if pid is not None:  # 用 taskkill 而不是 wmic ：为了保护某些系统程序
            result = 0 if os.system(f'taskkill /pid {pid} /F') else 1
        elif name:
            result = 0 if os.system(f'taskkill /im "{name}" /F') else 1
        else:
            result = 0
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def killTaskmgr(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        强制关闭任务管理器（单次）
        :param cmdObj: nothing
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        result = 0 if os.system('wmic process where name="Taskmgr.exe" delete') else 1
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def blockTaskmgr(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        禁止任务管理器启动（持续）
        :param cmdObj: block:是否禁止任务管理器启动(bool)
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        block = cmdObj.get('block')
        result = 0
        if block is not None:
            TaskmgrKiller.setKill(block)
            result = 1
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def clipboard(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> Union[str, int]:
        """
        设置剪切板
        :param cmdObj:  action:要执行的动作，可填写（右边字典的键）：{"clear":”清空“,"set":”设置剪贴板内容“, "get":"获取剪贴板内容"}
                        若 action 为 set 则需提供 content: 需要设置的内容(str)
        :param queue:   若 action 为 clear 与 set ： 1:成功, 0:失败
                        若 action 为 get ： JSON 对象 {"content":剪贴板内容字符串（若剪切板内容非字符串则为"None")}
        :return:        同 queue
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        action = cmdObj.get('action')
        content = cmdObj.get('content')
        if action == 'set':
            if content:
                pyperclip.copy(str(content))
                result = 1
            else:
                result = 0
        elif action == 'get':
            result = json.dumps({"content": pyperclip.paste()})
        elif action == 'clear':
            pyperclip.copy('')
            result = 1
        else:
            result = 0
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def memoryLook(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> str:
        """
        查看内存使用情况
        :param cmdObj:  nothing
        :param queue:   一个字符串化 JSON 数组，包括两个数字，第一个是仍未被使用的字节数，第二个是总字节数
        :return:        同 queue
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        men = psutil.virtual_memory()
        result = json.dumps((men.available, men.total))
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def queryProcess(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> str:
        """
        查看进程及其简单信息
        :param cmdObj:  all:是否显示全部的进程信息(bool),
                        若 all 为 False ，则可提供 pid: 查询进程的 PID(int),
                        若 all 为 False ，且 pid 未提供，则需提供 name: 查询进程的名字(str),
        :param queue:   tasklist 显示的字符串分析后的结果: [[映像名称(str), ProcessID(int), 会话名称(str), 内存占用(int, KB)], ...],
                        若 tasklist 查询不到进程，则为 [],
        :return:        同 queue
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        all_ = cmdObj.get('all')
        pid = cmdObj.get('pid')
        name = cmdObj.get('name')
        result = ''
        if all_ is not None:
            if all_:
                result = list(map(lambda processInfo: processInfo.toTuple(),
                                  ProcessQueryHelper.analyze(os.popen(f'tasklist').read())))
            else:
                if pid is not None:  # 有可能是0，不能简单"if pid:"
                    result = list(map(lambda processInfo: processInfo.toTuple(),
                                      ProcessQueryHelper.analyze(os.popen(f'tasklist /FI "pid eq {pid}"').read())))
                elif name:
                    result = list(map(lambda processInfo: processInfo.toTuple(),
                                      ProcessQueryHelper.analyze(
                                          os.popen(f'tasklist /FI "imagename eq {name}"').read())))
        queue.put(json.dumps(result)) if queue is not None else None
        return result

    @classmethod
    def startFile(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        以关联程序启动某一文件
        :param cmdObj: file:文件路径(str)
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        file: str = cmdObj.get('file')
        result = 0
        if file and osPath.exists(file):
            try:
                os.startfile(file)
                result = 1
            except Exception:
                traceback.print_exc(Config.errOutput)
                result = 0 if os.system("start \"" + file + "\"") else 1
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def surfWebsite(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        用浏览器访问一个网页
        :param cmdObj:  url:需要访问的网址（可不填写）(str),
                        若 url 不提供，则需提供 search:使用百度搜索的内容(str),
                        using:使用的浏览器（可不填，部分大小写，默认为 windows-default ）(str),
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        url = cmdObj.get('url')
        using = cmdObj.get('using') or 'windows-default'
        search = cmdObj.get('search')
        result = 0
        try:
            if url or search:
                browser = webbrowser.get(using)
                result = int(browser.open(url or f"https://www.baidu.com/s?{upa.urlencode(dict(wd=str(search)))}"))
        except webbrowser.Error:
            pass
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def getBrowsers(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> list:
        """
        获得本机可用的浏览器选项（用于surfWebsite命令）
        :param cmdObj: nothing
        :param queue: JSON 列表: [浏览器标识(str), ...]
        :return: 同queue
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        webbrowser.get()  # 初始化
        result = json.dumps(webbrowser._tryorder or [])
        queue.put(result) if queue is not None else None
        return queue

    @classmethod
    def fileDetail(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> dict:
        """
        获取文件信息
        :param cmdObj: path: 文件位置(str)
        :param queue: 文件信息 JSON 对象：{
                "available"(bool): 是否成功获取(若为 False 则后面几项为 None),
                "path"(str): 储存绝对路径,
                "name"(str): 文件名,
                "size"(int): 文件字节数,
                "md5": 文件内容 MD5 码(小写),
                "parts": 文件分块数量(由 size 和 fileTransportMaxSize 决定)(int)
            }
            若非文件、文件过大则返回对应空值的 JSON 对象
        :return:  同 queue
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)

        path = cmdObj.get("path")
        result = {
            "available": False,
            "path": "",
            "name": "",
            "size": 0,
            "md5": "",
            "parts": 0,
        }
        try:
            if path and osPath.isfile(path) and FileTransportHelper.checkFileSize(osPath.getsize(path)):
                path_pre, name = osPath.split(osPath.abspath(path))
                with open(path, 'rb') as r:
                    data = r.read()
                result["md5"] = MD5(data).hexdigest().lower()
                result["size"] = osPath.getsize(path)
                result["path"] = path_pre
                result['name'] = name
                result["available"] = True
                result["parts"] = FileTransportHelper.getTotalPart(result['size'])
        except PermissionError:
            pass
        queue.put(json.dumps(result)) if queue is not None else None
        return result

    @classmethod
    def fileTransport(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        传送部分文件, 由于有的文件过大会将内存撑爆，会禁止大文件读写
        :param cmdObj:  action:执行的动作（可为后面字典的键）(str)
                            {"post":"向服务器传送文件", "get":”从服务器中读取文件“.
                        若 action 为 post 则需提供 md5(str): 文件内容md5校对码 (小写) (base64处理前).
                        若 action 为 post 则需提供 data(str): base64处理后的文件内容.
                        若 action 为 post 则需提供 part(int, 从0开始): 传输的“部分”的序号
                        若 action 为 post 则需提供 name(str): 传送的文件的文件名.
                        若 action 为 post 则需提供 path(str): 传送的文件需存放的路径(无需文件名).
                        若 action 为 merge 则需提供 path(str): 需要合并的文件 (包括其路径与文件名, 不用加".part")
                        若 action 为 merge 则可提供 rewrite(bool, 默认为True): 是否重写.
                        若 action 为 get 则需提供 path(str): 传送的文件的文件路径(包括路径和文件名).
                        若 action 为 get 则需提供 part(int): 传送文件的分块序号(从一开始)
        :param queue:   若 action 为 get：
                            成功传输则为一个JSON字典(文件具体信息在 fileDetail 命令中提供)：
                                {
                                    "path"(str): 文件原路径(与 请求 相同),
                                    "data"(str): base64处理过的文件内容,
                                    "md5"(str): 文件对应内容 md5 校对码(小写),
                                    "part"(int): 文件分块序号(从1开始),
                                    "start"(int): 分块首字节在整个文件的位置,
                                    "state"(int): 传输状态码(见下)
                                }.
                            传输状态码：
                                1:获取成功;
                                0:文件内容传输失败（未知错误）;
                                3:不存在目标文件;
                                5:文件分块序号无效(或文件总内容过大);
                        若 action 为 post：
                            0:文件内容传输失败(原因未知);
                            1:文件成功接收且文件内容校验成功;
                            2:无效的储存路径,
                            4:md5校验失败;
                            5:文件分块过大;
                        若 action 为 merge:
                            0:文件合并失败(原因未知);
                            1:文件合并成功;
                            2:合并文件缺失或无效;
                            5:文件过大;
                            6:文件写入失败(rewrite为False且文件已存在时);
        :return:    1:传送成功, 0:传送失败（未知错误）, 2:无效的储存路径,
                    3:不存在目标文件, 4:md5校验失败, 5:文件范围无效(或文件过大),
                    6:文件写入失败(rewrite为False且文件已存在时)
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        action: str = cmdObj.get('action')
        md5Code: str = cmdObj.get('md5')
        rewrite: str = cmdObj.get('rewrite')
        part: int = cmdObj.get('part')
        data: str = cmdObj.get('data')
        name: str = cmdObj.get('name')
        path: str = cmdObj.get('path')
        result = 0
        queueResult = 0
        if action == 'post':
            if not osPath.exists(path):
                result = 2
            elif data:
                rawData = Encryptor.fromBase64(data.encode(Config.encoding))
                if len(rawData) > Config.fileTransportMaxSize:
                    result = 5
                else:
                    md5Value = MD5(rawData).hexdigest().lower()
                    if md5Value != md5Code:
                        result = 4
                    else:
                        with open(f'{osPath.join(path, name)}.part{part}', 'wb') as w:
                            w.write(rawData)
                        result = 1
            else:
                result = 4
            queueResult = result

        elif action == 'merge':
            if path:
                prefix, name = osPath.split(path)
                if not osPath.exists(prefix):
                    result = 2
                elif rewrite is False and osPath.exists(path):
                    result = 6
                else:
                    totalParts = FileTransportHelper.checkParts(prefix, name)
                    if totalParts:
                        rawData = b''
                        for i in range(totalParts):
                            if not FileTransportHelper.checkFileSize(len(rawData)):  # 检查读取内容是否符合要求
                                result = 5
                            if result == 0:  # 若文件读取大小仍可接收
                                with open(path + f".part{i}", 'rb') as r:
                                    rawData += r.read()  # 读取
                            try:
                                os.remove(path + f".part{i}")  # 尝试删除文件
                            except FileNotFoundError:
                                pass
                        if result == 0:  # 若无已知错误
                            with open(path, 'wb') as w:
                                w.write(rawData)  # 写入文件
                            result = 1
                    else:
                        result = 2
            else:
                result = 2

            queueResult = result

        elif action == 'get':
            queueResult = {
                "path": path,
                "data": "",
                "md5": "",
                "part": part,
                "start": 0,
                "state": 0
            }
            if not path or not osPath.isfile(path):  # 包含了存在检测
                queueResult["state"] = 3
                result = 3
            elif not (FileTransportHelper.checkPartRange(part, osPath.getsize(path)) and
                      FileTransportHelper.checkFileSize(osPath.getsize(path))):
                queueResult["state"] = 5
                result = 5
            else:
                start, length = FileTransportHelper.getPartRange(part)
                with open(path, 'rb') as r:
                    r.seek(start)
                    rawData = r.read(length)
                encodedData = Encryptor.toBase64(rawData).decode(Config.encoding)
                md5Code = MD5(rawData).hexdigest().lower()
                queueResult["md5"] = md5Code
                queueResult["data"] = encodedData
                queueResult["start"] = start
                queueResult["state"] = 1
                result = 1
        queueResult = json.dumps(queueResult)  # json化
        queue.put(queueResult) if queue is not None else None
        return result

    @classmethod
    def cancelShutdown(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        取消关机 todo 实现失败
        :param cmdObj: nothing
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        result = 0 if os.system('shutdown -a') else 1
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def shutdown(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        关机与定时关机
        :param cmdObj:  action(str): 从 close, restart, cancel, logout, rest 中选一个
                            close: 关机
                            restart: 重启
                            cancel: 取消计划关机
                            logout: 注销
                            rest: 休眠
                        delay(int, 秒): 执行延迟时间，默认为 0，只能与 close, retart 搭配
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        action = cmdObj.get('action')
        delay = cmdObj.get('delay')
        result = 0
        if action:
            switch = {
                'close': '-s',
                'restart': '-r',
                'logout': '-l',
                'cancel': '-a',
                'rest': "-h"
            }.get(action)
            if not switch:
                result = 0
            else:
                delaySwitch = f"-t {delay}" if delay else ""
                print(f'shutdown {switch} {delaySwitch}', file=Config.output)
                result = 0 if os.system(f'shutdown {switch} {delaySwitch}') else 1
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def inputLock(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        锁定输入 todo 锁定键盘模块
        :param cmdObj:  keyboard(bool): 是否锁定键盘
                        mouse(bool): 是否锁定鼠标
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        keyboard = cmdObj.get('keyboard')  # 难以实现
        mouse = cmdObj.get('mouse')
        if mouse is not None:
            InputLocker.setMouse(mouse)
        queue.put(1) if queue is not None else None
        return 1

    @classmethod
    def controlMouse(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        控制鼠标
        :param cmdObj:  action(enum[str]):  "moveBy": 鼠标相对位移
                                            "moveTo": 鼠标移动到绝对坐标
                                            "click": 鼠标按键单击
                                            "press": 鼠标按键按下
                                            "release": 鼠标按键松开
                                            "scroll": 鼠标滚轮
                        x(int): x 坐标, 若 action 为 moveBy 则 为相对移动坐标(正数向右)
                                                 为 moveTo 则为绝对坐标
                                                 为 scroll 则为水平方向的滚动距离(正数向右)
                                                 为其他则无需填写
                        y(int): y 坐标, 若 action 为 moveBy 则 为相对移动坐标(正数向下)
                                                 为 moveTo 则为绝对坐标
                                                 为 scroll 则为垂直方向的滚动距离(正数向上)
                                                 为其他则无需填写
                        button(int): 鼠标按键(0:左键,1 :中键, 2:右键), 只有在 action 为 click, press 或 release 时生效

                        若 action 为 click, 以下内容可填写:
                        clickDuration(int, ms): 鼠标单击时长, 默认为 50 (ms)
                        clickInterval(int, ms): 鼠标单击间隔, 默认为 20 (ms)
                        clickTimes(int): 鼠标单击次数, 默认为 1

                        以上参数默认选项触发条件: 没填写或参数值为 0
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        result = 0
        try:
            button = cmdObj.get("button")
            duration = cmdObj.get("clickDuration") or 50
            interval = cmdObj.get("clickInterval") or 20
            times = cmdObj.get("clickTimes") or 1
            action = cmdObj.get("action")
            x = cmdObj.get("x")
            y = cmdObj.get("y")

            if action == "moveBy":
                result = MouseController.moveBy((int(x), int(y)))
            elif action == "moveTo":
                result = MouseController.moveTo((int(x), int(y)))
            elif action == "click":
                result = MouseController.click(int(button), int(duration), int(times), int(interval))
            elif action == "press":
                result = MouseController.press(int(button))
            elif action == "release":
                result = MouseController.release(int(button))
            elif action == "scroll":
                result = MouseController.scroll((int(x), int(y)))
        except Exception:
            traceback.print_exc(file=Config.errOutput)
            result = 0
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def takePhoto(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        拍照或截屏并发送至邮箱
        :param cmdObj:  action(str): 从 photo, shortcut 中选择
                            photo: 用照相机拍照
                            shortcut: 屏幕截图
                        send(bool): 是否发送至邮箱
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        action = cmdObj.get('action')
        send = cmdObj.get('send')
        if action == 'photo':
            data = PictureSender.takePhoto()
        elif action == 'shortcut':
            data = PictureSender.takeShortcut()
        else:
            data = b''
        if data:
            if send:
                PictureSender.sendMsg(data)
            result = 1
        else:
            result = 0
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def execute(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        执行 python 语句
        :param cmdObj: content(str): 要执行的 python 语句
        :param queue: output(str): 标准输出流的输出, error(str): 标准异常流的输出
        :return: 1:命令成功执行而没有报错, 0:命令执行报错
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=Config.output)
        content = cmdObj.get('content')
        out, err = io.StringIO(), io.StringIO()
        stdout = sys.stdout
        stderr = sys.stderr
        sys.stdout = out
        sys.stderr = err
        try:
            exec(content)
            result = 1
        except Exception:
            err.write(traceback.format_exc())
            result = 0
        finally:
            sys.stdout = stdout
            sys.stderr = stderr
            out.seek(0)
            err.seek(0)
            print(out.read(), file=Config.output)
            print(err.read(), file=Config.errOutput)
        out.seek(0)
        err.seek(0)
        queue.put(json.dumps({"output": out.read(),
                              "error": err.read()})) if queue is not None else None
        return result

    @classmethod
    def getFunctionMap(cls):
        if not cls._functionMap:
            cls._functionMap = {
                'test': cls.test,
                'dir': cls.dir,
                'showText': cls.showText,
                'getDisks': cls.getDisks,
                'lockScreen': cls.lockScreen,
                'unlockScreen': cls.unlockScreen,
                'closeProgram': cls.closeProgram,
                'killTaskmgr': cls.killTaskmgr,
                'blockTaskmgr': cls.blockTaskmgr,
                'clipboard': cls.clipboard,
                'memoryLook': cls.memoryLook,
                'queryProcess': cls.queryProcess,
                'startFile': cls.startFile,
                'surfWebsite': cls.surfWebsite,
                'fileDetail': cls.fileDetail,
                'fileTransport': cls.fileTransport,
                'shutdown': cls.shutdown,
                'inputLock': cls.inputLock,
                'takePhoto': cls.takePhoto,
                'getBrowsers': cls.getBrowsers,
                'execute': cls.execute if Config.executeAvailable else None,
                'controlMouse': cls.controlMouse if Config.controlMouseAvailable else None,
            }
        return cls._functionMap


# 添加更多功能，并修改functionMap，并添加相应进程组

class InputLocker:
    """用于锁定鼠标和键盘输入"""
    mouseController = pynput.mouse.Controller()

    # @classmethod
    # def setKeyboard(cls, val: bool):
    #     pass

    @classmethod
    def setMouse(cls, val: bool):
        changeVar({'mouseLock': val})

    @classmethod
    def handle(cls):
        var = readVar()
        if var and var.get('mouseLock'):
            cls.mouseController.position = (0, 0)


class MouseController:
    """用于控制鼠标"""
    controller = pynput.mouse.Controller()
    buttons = {0: pynput.mouse.Button.left, 1: pynput.mouse.Button.middle, 2: pynput.mouse.Button.right}

    @classmethod
    def moveBy(cls, val: Tuple[int, int]):
        """
        使鼠标移动相对坐标
        :param val: (x 相对坐标, y 相对坐标)
        """
        cls.controller.move(*val)
        return 1

    @classmethod
    def moveTo(cls, val: Tuple[int, int]):
        """
        使鼠标移动到绝对坐标
        :param val: (x 绝对坐标, y 绝对坐标)
        """
        cls.controller.position = val
        return 1

    @classmethod
    def click(cls, button: int, duration: int, times: int, interval: int):
        """
        鼠标单击
        :param button: 0:左键, 1:中键, 2:右键
        :param duration: 单击时长 (ms)
        :param times: 单击次数
        :param interval: 单击间隔 (ms)
        :return: 是否成功单击(0:False, 1:True)
        """
        button = cls.buttons.get(button)
        if not button:
            return 0
        for i in range(times):
            cls.controller.press(button)
            time.sleep(duration * 0.001)
            cls.controller.release(button)
            time.sleep(interval * 0.001)
        return 1

    @classmethod
    def press(cls, button: int):
        """按下鼠标按键"""
        button = cls.buttons.get(button)
        cls.controller.press(button)
        return 1

    @classmethod
    def release(cls, button: int):
        """松开鼠标按键"""
        button = cls.buttons.get(button)
        cls.controller.release(button)
        return 1

    @classmethod
    def scroll(cls, val: Tuple[int, int]):
        """模拟鼠标滚轮"""
        cls.controller.scroll(*val)
        return 1


class BackgroundStopper:
    """
    通过 文件 关闭后台 RemoteControl
    """

    @staticmethod
    def checkVars():
        return osPath.exists(Config.variablesFile)

    @classmethod
    def canStop(cls):
        return not cls.checkVars()


class FileStoppingEvent(Exception):
    """通过文件关闭后台RemoteControl实例时产生"""
    pass


class TaskmgrKiller:
    kill = False
    lastKillTime = 0  # 上次关闭任务管理器时间
    lastReadTime = 0  # 上次读取var时间
    killSeparate = 0.5  # 秒
    readSeparate = 0.5  # 秒

    @classmethod
    def setKill(cls, kill: bool):
        changeVar({'blockTaskmgr': kill})

    @classmethod
    def readKill(cls):
        if cls.lastReadTime + cls.readSeparate < time.time():
            cls.lastReadTime = time.time()
            ifKill = readVar().get('blockTaskmgr')
            return ifKill

    @classmethod
    def handle(cls):
        cls.kill = bool(cls.readKill())
        if cls.kill and cls.lastKillTime + cls.killSeparate < time.time():
            cls.execKill()
            cls.lastKillTime = time.time()

    @staticmethod
    def execKill():
        os.popen('wmic process where name="Taskmgr.exe" delete')


if __name__ == '__main__':
    pass
