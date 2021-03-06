# coding=utf-8
import traceback


try:
    import sys

    sys.path.append(".")  # 解决src包导入问题
    from src.CommandExecutor import firstRun
    from src.Config import init, clearVar, hasInstance, switchesParse, Config
    from src.EventBus import EventBus
    import os


    def main():
        args = sys.argv
        os.chdir(os.path.split(args[0])[0])  # 防止别处启动搜索不到组件的异常
        switchesParse(args)  # 会对args进行改变
        if hasInstance():
            print("存在实例，正在退出...", file=Config.output)
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
except Exception:
    traceback.print_exc()
    input()
