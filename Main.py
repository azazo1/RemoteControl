# coding=utf-8
from src.CommandExecutor import firstRun
from src.Config import init, clearVar, hasInstance
from src.EventBus import EventBus
import os
import sys


def main():
    os.chdir(os.path.split(sys.argv[0])[0])  # 防止别处启动搜索不到组件的异常
    if hasInstance():
        return
    init()
    try:
        firstRun(sys.argv[1:])
        a = EventBus()
        a.loop()
    finally:
        clearVar()


if __name__ == '__main__':
    main()
