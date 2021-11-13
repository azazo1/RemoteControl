# coding=utf-8
import json
import multiprocessing
import os
import os.path as osPath
import subprocess
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
    def checkRange(cls, rangeObj) -> int:
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
    output = sys.stdout
    _lockScreenPath = None

    @classmethod
    def getLockScreenPath(cls):
        if not cls._lockScreenPath:
            cls._lockScreenPath = searchLockScreenDirPath()
            print("LockScreen 组件加载成功:", osPath.realpath(cls._lockScreenPath), file=cls.output)
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
            print('无效命令:', command, file=cls.output)
            queue.put(-1) if queue is not None else None
            return -1
        if func:
            return func(cmdObj, queue)
        else:
            print('无效命令:', command, file=cls.output)
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
        content = cmdObj.get('content')
        if content:
            print(content, file=cls.output)
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
                f'cd {cls.getLockScreenPath()}&&start "{sys.executable}" "LockScreen.pyw"')  # 启动锁屏
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
        try:
            os.chdir(cls.getLockScreenPath())
            from src.LockScreen.LockScreen import LoginManager
            LoginManager.flushLoginSituation(True)
            os.chdir(Config.originPath)
            result = 1
        except Exception:
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
        :param queue:   若 action 为 clear 与 get ： 1:成功, 0:失败
                        若 action 为 get ： JSON 对象 {"content":剪贴板内容字符串（若剪切板内容非字符串则为"None")}
        :return:        同 queue
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
        :param queue:   tasklist 显示的字符串,
                        若 tasklist 查询不到进程，则为 "None",
        :return:        同 queue
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
        all_ = cmdObj.get('all')
        pid = cmdObj.get('pid')
        name = cmdObj.get('name')
        result = ''
        if all_ is not None:
            if all_:
                result = os.popen(f'tasklist').read()
            else:
                if pid is not None:
                    result = os.popen(f'tasklist /FI "pid eq {pid}"').read()
                elif name:
                    result = os.popen(f'tasklist /FI "imagename eq {name}"').read()
        result = result if '=' in result else "None"
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def startProgram(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        启动某一可执行文件
        :param cmdObj: executable:可执行文件路径(str), args:执行参数（可不填）(str)
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
        executable: str = cmdObj.get('executable')
        args: str = cmdObj.get('args')
        result = 0
        if executable and osPath.exists(executable):
            subprocess.Popen(executable=executable, args=(args or '',), creationflags=subprocess.CREATE_NEW_CONSOLE)
            result = 1
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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
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
    def fileDetail(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> dict:
        """
        获取文件信息
        :param cmdObj: path: 文件位置(str)
        :param queue: 文件信息 JSON 对象：{
                "available": 是否成功获取(bool，若为 False 则后面几项为 None),
                "size": 文件字节数(int),
                "md5": 文件内容 MD5 码
            }
        :return:  同 queue
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)

        path = cmdObj.get("path")
        result = {"available": False, "size": None}
        if path and osPath.exists(path) and osPath.isfile(path):
            result["size"] = osPath.getsize(path)
            with open(path, 'rb') as r:
                data = r.read()
            result["md5"] = MD5(data).hexdigest()
            result["available"] = True
        queue.put(json.dumps(result)) if queue is not None else None
        return result

    @classmethod
    def fileTransport(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        传送部分文件
        :param cmdObj:  action:执行的动作（可为后面字典的键）(str)
                            {"post":"向服务器传送文件", "get":”从服务器中读取文件“.
                        若 action 为 post 则需提供 md5: 文件内容md5校对码（base64处理前）(str).
                        若 action 为 post 则需提供 data: base64处理后的文件内容(str).
                        若 action 为 post 则需提供 part: 传输的“部分”的序号(int, 从0开始)
                        若 action 为 post 则需提供 name: 传送的文件的文件名(str).
                        若 action 为 post 则需提供 path: 传送的文件需存放的路径（无需文件名）(str).
                        若 action 为 merge 则需提供 path: 需要合并的文件(str, 包括其路径, 不用加".part")
                        若 action 为 merge 则可提供 rewrite: 是否重写(bool, 默认为True).
                        若 action 为 get 则需提供 path: 传送的文件的文件路径(str).
                        若 action 为 get 则需提供 range: 传送的文件的字节范围，1为起始，左闭右闭，范围不应超过最大传输文件限制(list[int, int]).
        :param queue:   若 action 为 get：
                            成功传输则为一个JSON字典：
                                {
                                    "name": 文件名(str),
                                    "data": base64处理过的文件内容(str),
                                    "md5": 文件对应内容 md5 校对码 (str)
                                }.
                            传输失败则为：
                                0:文件内容传输失败（未知错误）;
                                3:不存在目标文件;
                                5:文件范围无效(或过大);
                        若 action 为 post：
                            0:文件内容传输失败;
                            1:文件成功接收且文件内容校验成功;
                            2:无效的储存路径,
                            4:md5校验失败;
                            5:文件过大;
                        若 action 为 merge:
                            0:文件合并失败;
                            1:文件合并成功;
                            2:合并文件缺失或无效;
                            6:文件写入失败(rewrite为False且文件已存在时);
        :return:    1:传送成功, 0:传送失败（未知错误）, 2:无效的储存路径,
                    3:不存在目标文件, 4:md5校验失败, 5:文件范围无效(或过大),
                    6:文件写入失败(rewrite为False且文件已存在时)
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
        action: str = cmdObj.get('action')
        md5Code: str = cmdObj.get('md5')
        rewrite: str = cmdObj.get('rewrite')
        part: int = cmdObj.get('part')
        data: str = cmdObj.get('data')
        name: str = cmdObj.get('name')
        path: str = cmdObj.get('path')
        range_: List[int, int] = cmdObj.get('range')
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
                    md5Value = MD5(rawData).hexdigest()
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
                            with open(path + f".part{i}", 'rb') as r:
                                rawData += r.read()
                            os.remove(path + f".part{i}")
                        with open(path, 'wb') as w:
                            w.write(rawData)
                        result = 1
                    else:
                        result = 2
            else:
                result = 2

            queueResult = result

        elif action == 'get':
            if not path or not osPath.isfile(path):
                result = 3
                queueResult = 3
            elif not FileTransportHelper.checkRange(range_):
                result = 5
                queueResult = 5
            else:
                left, right = range_
                with open(path, 'rb') as r:
                    r.seek(left - 1)
                    rawData = r.read(right - left + 1)
                encodedData = Encryptor.toBase64(rawData).decode(Config.encoding)
                md5Code = MD5(rawData).hexdigest()
                name = osPath.split(path)[-1]
                queueResult = json.dumps(
                    {'name': name, "data": encodedData, 'md5': md5Code}
                )
                result = 1

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
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
        result = 0 if os.system('shutdown -a') else 1
        queue.put(result) if queue is not None else None
        return result

    @classmethod
    def launchOnStart(cls, cmdObj: Dict, queue: Union[multiprocessing.Queue, MyThreadQueue] = None) -> int:
        """
        设置开机自启动
        :param cmdObj: launch:是否开机自启动
        :param queue: 1:成功, 0:失败
        :return: 1:成功, 0:失败
        """
        print(f'任务 {cmdObj.get("type")} 执行', file=cls.output)
        launch = cmdObj.get('launch')
        result = 0
        if launch is not None:
            if launch:
                result = 0 if os.system(  # 创建新任务(覆盖)
                    f'''schtasks /create /tn RemoteControl /sc minute /tr "{sys.argv[0].strip('"')}" /f'''
                ) else 1
            else:
                result = 0 if os.system(  # 删除旧任务(覆盖)
                    f'''schtasks /delete /tn RemoteControl /f'''
                ) else 1
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
                print(f'shutdown {switch} {delaySwitch}')
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
        keyboard = cmdObj.get('keyboard')  # 难以实现
        mouse = cmdObj.get('mouse')
        if mouse is not None:
            InputLocker.setMouse(mouse)
        queue.put(1) if queue is not None else None
        return 1

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
                'startProgram': cls.startProgram,
                'surfWebsite': cls.surfWebsite,
                'launchOnStart': cls.launchOnStart,
                'fileDetail': cls.fileDetail,
                'fileTransport': cls.fileTransport,
                'shutdown': cls.shutdown,
                'inputLock': cls.inputLock,
                'takePhoto': cls.takePhoto,
            }
        return cls._functionMap


# 添加更多功能，并修改functionMap，并添加相应进程组

class InputLocker:
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

# if __name__ == '__main__':
#     process = Executor.subProcessExec("""{"type":"test", "content":"hello!"}""")
#     Executor.closeProcesses()
#     print(process.exitcode)
