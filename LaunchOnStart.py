# coding=utf-8
"""
Please lay this file in the same path as Main.py or Main.pyw.
请将本文件放在与Main.py或Main.pyw同路径下
"""
import ctypes
import os.path as osPath
import sys
import traceback

import win32api
import win32con

if not ctypes.windll.shell32.IsUserAnAdmin():
    # Code of your program here else: # Re-run the program with admin rights
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
    quit()

KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
KEY_VALUE_NAME = "RemoteControl"


def launchOnStart(launch: bool, quiet: bool = None):
    """
    开机自启动（注册表实现）
    :param launch: 是否自启动
    :param quiet: 若启动，是否静默启动（可不填，默认）
    :return:
    """
    print(f'任务 launchOnStart 执行')
    try:
        key = win32api.RegOpenKey(win32con.HKEY_LOCAL_MACHINE, KEY,
                                  0, win32con.KEY_ALL_ACCESS)
        if launch:
            if quiet is None:
                quiet = False  # 默认值
            filenamePrefix = osPath.split(__file__)[0]  # 获取当前文件下路径
            filename = osPath.join(filenamePrefix, 'Main.pyw') if quiet else osPath.join(
                filenamePrefix, "Main.py")
            win32api.RegSetValueEx(key, KEY_VALUE_NAME, 0, win32con.REG_SZ, f"\"{filename}\"")
            # 旧实现
            # s = f'''schtasks /create /tn RemoteControl /sc minute /tr "cmd /k \\"{execFilename}\\" \\"{filename}\\"" /f'''
            # result = 0 if os.system(  # 创建新任务(覆盖)
            #     s
            # ) else 1
        else:
            win32api.RegDeleteValue(key, KEY_VALUE_NAME)
            # 旧实现
            # result = 0 if os.system(  # 删除旧任务(覆盖)
            #     f'''schtasks /delete /tn RemoteControl /f'''
            # ) else 1
        print("成功修改！")
    except Exception:
        traceback.print_exc()


if __name__ == '__main__':
    get = input("是否自启动？(yq:是,且静默启动/y:是,但不静默启动/n:否,并关闭自启动):")
    if get == 'yq':
        launchOnStart(True, True)
    elif get == "y":
        launchOnStart(True, False)
    elif get == "n":
        launchOnStart(False)
    else:
        print("无效输入")
    input("退出")
