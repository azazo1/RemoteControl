# coding=utf-8
import LockScreen

if __name__ == '__main__':
    try:
        LockScreen.main()
    except Exception as e:
        LockScreen.tkmsg.showerror(type(e), LockScreen.traceback.format_exc())
