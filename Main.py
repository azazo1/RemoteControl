# coding=utf-8
from src.CommandExecutor import firstRun
from src.Config import init, clearVar, hasInstance, switchesParse
from src.EventBus import EventBus
import os
import sys


def main():
    args = sys.argv
    os.chdir(os.path.split(args[0])[0])  # 防止别处启动搜索不到组件的异常
    switchesParse(args)  # 会对args进行改变
    if hasInstance():
        return
    init()
    try:
        firstRun(args[1:])
        a = EventBus()
        a.loop()
    finally:
        clearVar()


if __name__ == '__main__':
    main()
