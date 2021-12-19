# coding=utf-8
import json
import multiprocessing
import socket
import sys
import threading
import time
import traceback
from hashlib import md5
from threading import Thread
from typing import List, Dict

from src.CommandExecutor import Executor, MyProcess, MyThreadQueue
from src.Config import Config
from src.Encryptor import Encryptor


def filterNotTrue(obj: List[bytes]):
    return list(filter(lambda a: bool(a) and not a.isspace(), obj))


class AuthenticateError(Exception):
    pass

def get_host_ip():
    """
    查询本机ip地址
    """
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.connect(('8.8.8.8',80))
        ip=s.getsockname()[0]
    finally:
        s.close()

    return ip

class ClientManager:
    def __init__(self, client: socket.socket, address: tuple):
        self.alive = True
        self.authenticated = None  # None:未鉴权 False:鉴权失败 True:鉴权成功
        self.address = address
        self.socket = client
        self.lineBuf: bytes = b''  # 未接收完全的单行
        self.bufLines: List[bytes] = []  # 仍未取出的行
        self.communicate: List[MyProcess, multiprocessing.Queue] = []
        self.thread = Thread(target=self.loop, daemon=True)
        self.thread.start()
        self.output = sys.stdout

    def _initSocket(self):
        self.socket.setblocking(False)

    def authenticate(self, line: bytes):
        """
        鉴权，验证此连接是否有效
        :param line:序列化的 JSON 字典
                        name(str): 项目名
                        version(str): 版本号
                        stamp(int): 时间戳（毫秒）
                        md5(str): md5(name+version+密钥+stamp)
        :return: None
        """
        try:
            obj: dict = json.loads(line)
            name: str = obj.get('name')
            version: str = obj.get('version')
            stamp: int = obj.get('stamp')
            md5_: str = obj.get('md5')
            if (name == Config.name
                    and version == Config.version
                    and (time.time() * 1000 // 1 < Config.authenticationTimeoutMilli + stamp)
                    and md5((Config.name + Config.version + Config.key.decode(Config.encoding) + str(
                        stamp)).encode(Config.encoding)).hexdigest() == md5_
            ):
                self.authenticated = True
                print(f'{self.address} 登录成功', file=self.output)
                self.sendLine(b'1', encrypt=False)
            else:
                raise AuthenticateError()
        except Exception as e:
            print(f'{self.address} 登录失败 {type(e)}', file=self.output)
            self.authenticated = False
            self.sendLine(b'0', encrypt=False)

    def loop(self):
        while self.alive:
            time.sleep(1 / Config.loopingRate)
            line = self.readLine()
            if not line or line.isspace():
                continue
            if self.authenticated is None:
                self.authenticate(line)
            elif self.authenticated:
                command = Encryptor.decryptFromBase64(line)
                command = command.decode(Config.encoding)
                if Config.usingMultiprocessing:
                    process, queue = Executor.subProcessExec(command)
                    Thread(target=self.handleTaskOfProcess, args=(process, queue), daemon=True).start()  # 交给子线程处理任务
                else:
                    thread, queue = Executor.threadExec(command)
                    Thread(target=self.handleTaskOfThread, args=(thread, queue), daemon=True).start()  # 交给子线程处理任务
            else:
                self.close()

    def handleTaskOfProcess(self, process: MyProcess, queue: multiprocessing.Queue):
        """等待任务执行完成，并将结果发送至客户端 多进程模式"""
        while process.is_alive():
            if not queue.empty():
                get = queue.get()
                self.sendLine(str(get).encode(Config.encoding))

    def handleTaskOfThread(self, process: Thread, queue: MyThreadQueue):
        """等待任务执行完成，并将结果发送至客户端 多线程模式"""
        while process.is_alive():
            if queue:
                get = queue.get()
                self.sendLine(str(get).encode(Config.encoding))
            time.sleep(1 / Config.loopingRate)
        while queue:  # 尝试将剩余的发送
            get = queue.get()
            self.sendLine(str(get).encode(Config.encoding))

    def sendLine(self, data: bytes, encrypt: bool = True):
        """发送一条转换为base64编码的消息"""
        if not self.alive:
            return
        data_info = data[:Config.networkIOInfoMaxLength//2]+b"..."+data[max(Config.networkIOInfoMaxLength//2, len(data)-Config.networkIOInfoMaxLength//2):] if len(data) > Config.networkIOInfoMaxLength else data
        data = Encryptor.encryptToBase64(data) if encrypt else data
        data += b'\n'
        if len(data) > Config.longestCommand:
            print(f"[失败:过长] 发送 长度:{len(data)} 内容:{data_info} 到 {self.address}", file=self.output)
            return
        try:
            block = self.socket.getblocking()
            self.socket.setblocking(True)
            self.socket.sendall(data)
            self.socket.setblocking(block)
            print(f"[成功] 长度:{len(data)} 内容:{data_info} 到 {self.address}", file=self.output)
        except Exception:
            print(f"[失败:异常] 长度:{len(data)} 内容:{data_info} 到 {self.address}", file=self.output)
            self.close()

    # def isAlive(self):
    #     return self.alive
    #     测试连接是否正常
    #     try:
    #         self.socket.send(b' ')
    #         return True
    #     except ConnectionError:
    #         return False
    #     except (BlockingIOError, socket.timeout):
    #         return True

    def readLine(self) -> bytes:
        """读取一行,若未到一行则返回空bytes"""
        if not self.alive:
            return b''
        try:
            getBytes = self.socket.recv(Config.readRange)
            if getBytes == b'' and not self.bufLines:
                self.alive = False
                # raise ConnectionAbortedError('连接断开')
        except (socket.timeout, BlockingIOError):
            getBytes = b''
        except ConnectionError:
            getBytes = b''
            self.alive = False
        if getBytes.find(b'\n') != -1:
            lines = getBytes.split(b'\n')
            self.bufLines.extend(filterNotTrue([self.lineBuf + lines[0]]))
            self.lineBuf = b''
            if getBytes.endswith(b'\n'):
                self.bufLines.extend(filterNotTrue(lines[1:]))
            else:
                self.bufLines.extend(filterNotTrue(lines[1:-1]))
                self.lineBuf = lines[-1]
        else:
            self.lineBuf += getBytes
        try:
            result = self.bufLines.pop(0)
        except IndexError:
            result = b''
        if result:
            if len(result) > Config.longestCommand:  # 清除长命令
                result = b''
            else:
                try:
                    data = Encryptor.decryptFromBase64(result)
                    data = f"{data[:Config.networkIOInfoMaxLength//2]}...{data[max(Config.networkIOInfoMaxLength//2, len(data)-Config.networkIOInfoMaxLength//2):]}" if len(data) > Config.networkIOInfoMaxLength else data
                    print("接收到：来自{from_}，长度：{length}，内容（已解码）：{data}"
                          .format(length=len(data), from_=self.address, data=data), file=self.output
                          )
                except Exception:
                    data = result
                    data = data[:Config.networkIOInfoMaxLength//2] +b"..."+ data[max(Config.networkIOInfoMaxLength//2, len(data)-Config.networkIOInfoMaxLength//2):] if len(data) > Config.networkIOInfoMaxLength else data
                    print("接收到：来自{from_}，长度：{length}，内容（原始）：{data}"
                          .format(length=len(data), from_=self.address, data=data), file=self.output
                          )
        return result

    def getPeerName(self):
        return self.address

    def close(self):
        self.alive = False
        try:
            self.socket.close()
        except Exception:
            pass
        try:
            if threading.current_thread().ident != self.thread.ident:
                self.thread.join()
        except Exception:
            pass

    def __del__(self):
        if self.alive:
            self.close()


class SocketServer:
    def __init__(self):
        self.alive = True
        self.output = sys.stdout
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clientManagers: Dict[tuple, ClientManager] = {}
        self._initSocket()

    def close(self):
        self.alive = False
        print('服务器关闭', file=self.output)
        self.closeClients()
        self.socket.close()

    def closeClients(self):
        map(lambda i: i.close(), self.clientManagers.values())

    def handle(self):
        self.accept()
        self.clearDeadClient() if Config.clearDeadClient else None

    def _initSocket(self):
        self.socket.bind(("0.0.0.0", 2004))
        self.socket.listen()
        self.socket.setblocking(False)
        print(f'服务器开启，开启于{(get_host_ip(), self.socket.getsockname()[-1])}',
              file=self.output)

    def accept(self):
        try:
            client, address = self.socket.accept()
            self.clientManagers[address] = ClientManager(client, address)
            # print(f'{address} 连接', file=self.output)
        except (BlockingIOError, socket.timeout):
            pass

    def clearDeadClient(self):
        delete = []
        for address, clientManager in self.clientManagers.items():
            if not clientManager.alive:
                delete.append(address)
        for address in delete:
            print(f'{address} 断开', file=self.output) if self.clientManagers[address].authenticated else None
            self.clientManagers.pop(address)

    def getClientManager(self, address: tuple):
        return self.clientManagers.get(address)

    def __del__(self):
        if self.alive:
            self.close()
# def main():
#     ss = SocketServer()
#     while ss.alive:
#         ss.accept()
#         for clientManager in ss.clientManagers.values():
#             get = clientManager.readLine()
#             print(get) if get else None
#         ss.clearDeadClient()
#         time.sleep(0.5)
#
#
# if __name__ == '__main__':
#     main()
