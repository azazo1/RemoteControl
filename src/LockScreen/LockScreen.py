# coding=utf-8
import json
import socket
import traceback
from PIL import Image, ImageTk
from win32gui import GetForegroundWindow as getWindow
from sys import argv
import os
import tkinter as tk
import tkinter.messagebox as tkmsg
import hashlib
import time
import re

loopingRate = 60
waitTime = 0.05  # 公用等待时间
ifLog = False


def log(msg: str):
    if not ifLog:
        return
    with open('log.txt', 'a') as w:
        w.write(msg + '\n')


def whileNoPython():
    get = os.popen('wmic process where name="python.exe"').read()
    get2 = os.popen(f'wmic process where name="{argv[0]}"').read()
    get3 = os.popen(f'wmic process where name="pythonw.exe"').read()
    count = len(re.findall(r'"(.+)"', get))
    count += len(re.findall(r'"(.+)"', get2))
    count += len(re.findall(r'"(.+)"', get3))
    if count <= 1:
        LoginManager.deleteCache()


def encryptByMP5(str1: str) -> str:
    md5 = hashlib.md5(str1.encode())
    return md5.hexdigest()


def encryptByCode(origin: bytes, code: str) -> bytes:
    get = []
    for a in origin:
        now = a
        for i, b in enumerate(code):
            now ^= ord(b) + i  # 对单个字符加密
        get.append(now)
    return bytes(get)


def decryptByCode(origin: bytes, code: str) -> bytes:
    get = []
    for a in origin:
        now = a
        for i, b in enumerate(code):
            now ^= ord(b) + i  # 对单个字符加密
        get.append(now)
    return bytes(get)


class Configure:
    DEFAULT = 0
    TEST = 1

    def __init__(self, loadType=DEFAULT):
        self.type = loadType
        self.configureFile = 'PasswordConfiguration.azo'
        self.cacheFile = 'cache'
        self._con: dict

    def getAttr(self, item):
        try:
            return self._con[item]
        except KeyError:
            try:
                # print('NoThisName:' + item + ', try to use the default one.', file=sys.stderr)
                return None
            except KeyError:
                # print(f'StillNoThisName:{item}', file=sys.stderr)
                pass

    def initCon(self):
        try:
            with open(self.configureFile, 'r') as r:
                # noinspection PyAttributeOutsideInit
                self._con = json.load(r)
        except FileNotFoundError:
            pass


class PasswordManager:
    con = Configure()
    con.initCon()

    def __init__(self):
        self.__password = self.con.getAttr('EncryptedPassword')  # md5加密后的密码
        self._filepath = self.con.getAttr('PasswordFilePath')  # 读取密码文件位置
        self._pngpath = self.con.getAttr('PicturePaths')  # 末尾显示图片文件位置
        self._pngName = self.con.getAttr('PictureName')  # 末尾显示图片文件

    def getFilePath(self, disk):
        return self._filepath.format(disk)

    def getCon(self, item):
        return self.con.getAttr(item)

    def check(self, password: str):
        return encryptByMP5(password) == self.__password

    def checkFile(self):
        get = ''
        for char in range(65, 65 + 26):
            try:
                with open(self.getFilePath(chr(char)), 'r') as r:
                    get = r.read()
            except Exception:
                pass
        return encryptByMP5(get) == self.__password or LoginManager.readLoginSituation()


class LoginManager(PasswordManager):
    def __init__(self):
        super(LoginManager, self).__init__()

    @classmethod
    def getCode(cls):
        t = time.time() // (waitTime * 1000)  # n秒更新一次密码
        # f'MadeByAzazo1{t}'
        return f'{t}'

    @classmethod
    def flushLoginSituation(cls, sit: bool):
        with open(cls.con.cacheFile, 'wb') as w:
            write = encryptByCode(b'True' if sit else b'False', cls.getCode())
            w.write(write)
            log(f'{write=}, {cls.getCode()=}, {sit=}')
        return write

    @classmethod
    def readLoginSituation(cls):
        try:
            with open(cls.con.cacheFile, 'rb') as r:
                read = r.read()
                get = decryptByCode(read, cls.getCode())
            log(f'{read=}, Supposed:{encryptByCode(b"True", cls.getCode())}, '
                f'{cls.getCode()=}, {get == b"True"}')
            if get == b'True':
                return True
        except FileNotFoundError:
            # print('no cache for the time being.', file=sys.stderr)
            return False
        except Exception:
            # traceback.print_exc()
            return False

    @classmethod
    def deleteCache(cls):
        try:
            p = cls.con.cacheFile
            os.remove(p) if cls.con.getAttr('DeleteCache') else None
        except FileNotFoundError:
            pass


class RemoteLoginManager(LoginManager):
    def __init__(self):
        super().__init__()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def detectRemoteMessage(self):
        # try:
        #     # data = self.server.recvfrom(1024)
        #     if self.check(data[0].decode()):
        #         self.flushLoginSituation(True)
        #         return True
        # except socket.error:
        return False

    def __del__(self):
        self.close()

    def close(self):
        # self.server.close()
        pass


class GUIBuilder(PasswordManager):
    def __init__(self):
        super().__init__()
        self.root: tk.Tk = None
        self.entry = None
        self.label = None
        self.text = None
        self.wrongtimes = 0
        self.alive = True
        self.img = None
        self.originWindows = [getWindow()]
        self._topMost = self.con.getAttr('TopMost')
        self._fullScreen = self.con.getAttr('FullScreen')
        self._maxWrongTimes = self.con.getAttr('MaximumWrongTimes')
        self._closable = self.con.getAttr('Closable')
        self._killTaskManager = self.con.getAttr('KillTaskManager')
        self._restart = self.con.getAttr('Restart')
        self.remoteLogin = RemoteLoginManager()
        # if not LoginManager.readLoginSituation():
        #     LoginManager.flushLoginSituation(False)

    def getSetImage(self):
        for p in self._pngpath:
            try:
                pic = os.path.join(p, self._pngName)
                im = Image.open(pic)
                im.resize((self.root.winfo_screenwidth(), self.root.winfo_screenheight()), Image.ANTIALIAS)
                self.img = ImageTk.PhotoImage(im)
                return self.img
            except Exception:
                # print("Img_path:" + p, file=sys.stderr)
                # traceback.print_exc()
                pass

    def putWords(self, words, wait=0.0):
        self.text['text'] += words
        if len(self.text['text'].split('\n')) > 7:  # 消息显示最大行数
            self.text['text'] = '\n'.join(self.text['text'].split('\n')[1:])
        self.root.update()
        time.sleep(wait)

    def clearWords(self):
        self.text['text'] = ''

    def closecomputer(self):
        os.system('shutdown -s -t 10')
        self.close()

    def rightpass(self):
        self.label['text'] = f'Welcome!'
        self.root.update()

    def close(self):
        LoginManager.deleteCache()
        self.alive = False
        self.root.destroy()

    def check(self, password: str, goPass=False):
        if (
                (not LoginManager.readLoginSituation())
                and (not super().check(password))
                and (not self.checkFile())
                and (not goPass)
        ):
            self.entry.delete(0, tk.END)
            self.wrongtimes += 1
            self.label['text'] = f"Wrong Password! This is the {self.wrongtimes} times."
            if self.wrongtimes >= self._maxWrongTimes:
                self.closecomputer()
        else:
            self.rightpass()
            os.system('shutdown -a')
            LoginManager.flushLoginSituation(True)
            self.root.update()

    def showPic(self):
        # 取下所有元素
        for item in list(self.root.children.values())[::-1]:  # 倒序迭代窗口中元素
            item.forget()
            self.root.update()
        label = tk.Label(self.root, image=self.img, background='#000000')
        label.pack(fill=tk.BOTH, expand=True)
        self.root.update()

    def getWindow(self):
        self.originWindows.append(getWindow())
        self.text['text'] += f'[INFO] {time.asctime()} Get Window Successfully\n'
        self.root.bind('<Enter>', lambda *args: None)  # 防止第二次更新

    def buildWindow(self):
        self.root = root = tk.Tk()
        self.root.update()
        self.label = tk.Label(root, text='Hello, please input my password. '
                                         'If you want to quit, '
                                         'just close the computer in a correct way.\n'
                                         f'If you have a Key File in Correct Path: {self.getFilePath("E")}, '
                                         f'just click Verify.')
        self.label.pack(fill=tk.BOTH, expand=True)  # 提示信息
        self.entry = entry = tk.Entry(root, show='*')
        entry.pack(fill=tk.X, expand=True)

        buttonframe = tk.Frame(root)
        buttonframe.pack(fill=tk.BOTH, expand=True)

        self.text = text = tk.Label(
            root,
            height=10,  # 消息框占用行数
            text='',
        )
        text.pack(expand=True, fill=tk.BOTH)

        tk.Button(  # 确认按钮
            buttonframe,
            text='Verify',
            background='#ffff00',
            command=lambda: self.check(entry.get())
        ).pack(side=tk.LEFT, expand=True)

        tk.Button(  # 关机按钮
            buttonframe,
            text='Close Computer',
            background='#ff0000',
            command=self.closecomputer
        ).pack(side=tk.LEFT, expand=True)

        entry.focus()
        entry.bind('<Return>', lambda *arg: self.check(entry.get()))
        entry.bind('<Escape>', lambda *arg: self.closecomputer())

        root.title(argv[0].split('\\')[-1])
        root.bind('<Enter>', lambda *a: self.getWindow())  # 通过鼠标悬浮获取当前窗口句柄
        root.protocol("WM_DELETE_WINDOW", lambda: None) if not self._closable else None
        root.attributes("-fullscreen", self._fullScreen)
        root.attributes("-topmost", self._topMost)
        self.getSetImage()  # 读取图片

    def looping(self):
        if not self.alive:
            raise RuntimeError('It has already close!')

        self.buildWindow()
        try:
            lastLoadTime = 0
            while self.alive:
                time.sleep(1 / loopingRate)
                nowTime = time.time()
                self.root.update()
                # 注意两个if语句不要交换位置，
                # 不然用按钮检测密码会导致失焦而新开窗口
                if nowTime > lastLoadTime + waitTime * 10:
                    os.system('wmic process where Name="Taskmgr.exe" delete') if self._killTaskManager else None
                    if not self.checkFile():
                        self.putWords(f'[INFO] {time.asctime()} Load File Failed.\n')
                    else:
                        self.endShow()
                        self.showPic()
                        break
                    lastLoadTime = nowTime
                if getWindow() not in self.originWindows:  # 检测到窗口离开，重新启动程序
                    self.text['text'] += f'[INFO] {time.asctime()} {getWindow(), self.originWindows}\n'
                    self.remoteLogin.close()
                    os.system(f'"{argv[0]}"') if self._restart else None  # 新建进程
                    break

        finally:
            self.close()

    def endShow(self):
        wait = waitTime
        self.clearWords()
        self.putWords(f'[INFO] {time.asctime()} Load File Successfully!\n', wait)
        self.putWords(f'[INFO] {time.asctime()} File Reading...', wait)
        self.putWords(f'Read It!\n', wait)
        self.putWords(f'[INFO] {time.asctime()} Password Parsing...', wait)
        self.putWords(f'Parsed It!\n', wait)
        self.putWords(f'[INFO] {time.asctime()} Password is Corrected.\n', wait)
        self.putWords(f'[INFO] {time.asctime()} Welcome to use Azazo1\'s Computer.\n', wait)


def main():
    LoginManager.flushLoginSituation(True)
    time.sleep(0.5)
    LoginManager.deleteCache()
    g = GUIBuilder()
    g.looping()


def test():
    a = RemoteLoginManager()
    while True:
        print(True) if a.detectRemoteMessage() else None


# def test():
#     LoginManager.flushLoginSituation(True)
#     print(LoginManager.readLoginSituation())
#     LoginManager.flushLoginSituation(False)
#     print(LoginManager.readLoginSituation())
#     LoginManager.flushLoginSituation(True)
#     time.sleep(5)
#     print(LoginManager.readLoginSituation())  # 五秒后的过期登录状态


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        tkmsg.showerror(type(e), traceback.format_exc())
