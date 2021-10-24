# coding=utf-8
import sys
import time

from src.CommandExecutor import Executor, TaskmgrKiller, InputLocker
from src.Config import Config
from src.ServerSocket import SocketServer


class EventBus:
    def __init__(self):
        self.server = SocketServer()
        self.alive = True
        self.output = sys.stdout

    def loop(self):
        try:
            while self.alive:
                self.server.handle()
                TaskmgrKiller.handle()
                InputLocker.handle()
                time.sleep(1 / Config.loopingRate)
        except KeyboardInterrupt:
            print('用户关闭了脚本', file=self.output)
        finally:
            self.close()

    def close(self):
        self.alive = False
        Executor.closeProcesses(True)
        self.server.close()

    def __del__(self):
        if self.alive:
            self.close()

# if __name__ == '__main__':
#     a = EventBus()
#     a.loop()
