# coding=utf-8
import os
import sys
import time

from src.CommandExecutor import Executor, TaskmgrKiller, InputLocker, BackgroundStopper, FileStoppingEvent
from src.Config import Config
from src.ServerSocket import SocketServer


class EventBus:
    def __init__(self):
        self.server = SocketServer()
        self.alive = True

    def loop(self):
        try:
            while self.alive:
                os.chdir(Config.originPath)  # 防止executor改变路径
                if BackgroundStopper.canStop():
                    raise FileStoppingEvent()
                self.server.handle()
                TaskmgrKiller.handle()
                InputLocker.handle()
                time.sleep(1 / Config.loopingRate)
        except KeyboardInterrupt:
            print('用户关闭了脚本', file=Config.output)
        except FileStoppingEvent:
            print('用户通过文件关闭了脚本', file=Config.output)
        finally:
            self.close()

    def close(self):
        self.alive = False
        Executor.closeProcesses(True)
        self.server.close()

    def __del__(self):
        try:
            if self.alive:
                self.close()
        except AttributeError:
            pass

# if __name__ == '__main__':
#     a = EventBus()
#     a.loop()
