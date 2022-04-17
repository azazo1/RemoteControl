RemoteControl
=============

这是一个方便地使用手机管理电脑的软件  
功能如下:

1. 剪切板处理
2. 文件传输
3. 进程管理
4. 内存使用情况查看
5. 关闭程序
6. 启动程序
7. 使用浏览器打开网页
8. 关机
9. 拍照、截屏
10. 显示文字
11. 锁定 / 解锁 屏幕

等

*需要配套对应版本 **RemoteControlClient** 使用*

## 安装

1. 若您未安装过 [python 3.8.1](https://www.python.org/ftp/python/3.8.1/python-3.8.1-amd64.exe):
    1. 您可以打开 [setupPython.cmd](setupPython.cmd) 下载并安装,但下载过程稍慢
    2. 您也可以点击上面的链接将 python 安装包下载至 RemoteControl 根目录,然后启动 [setupPython.cmd](setupPython.cmd) 进行安装

   此时无需启动 [prepare.py](prepare.py)
2. 若您安装了 [python 3.8.1](https://www.python.org/ftp/python/3.8.1/python-3.8.1-amd64.exe):  
   你可以启动 [prepare.py](prepare.py) 来安装依赖包,等待 *Over* 字样出现即为安装成功

## 启动

1. 您可以启动 [Main.py](Main.py) 显式启动,此时将会弹出一个命令行窗口
2. 您也可以启动 [Main.pyw](Main.pyw) 隐式启动,此时本软件将会在后台静默运行
3. 您也可以在 [Main.py](Main.pyw) 或 [Main.pyw](Main.pyw) 后加上要执行的命令,使其在启动后得到立即执行,如:  
   `python.exe Main.py "{\"type\":\"test\", \"content\":\"Hello World!\"}"`
4. 本软件只允许一个实例运行,若您想重新运行:  
   可以在启动文件 ([Main.py](Main.py)/[Main.pyw](Main.pyw)) 后加上参数 -F 强制重新启动,即:  
   `python.exe Main.py -F`

## 关闭程序

1. 您可以在显式启动实例的命令行中使用 *Ctrl + C* 快捷键关闭
2. 您也可以启动 [TerminateMain.py](TerminateMain.py) 关闭正在运行的实例
3. 请不要直接点击 X 关闭实例命令行

## 开机自启动

1. 以管理员身份启动 [LaunchOnStart.py](LaunchOnStart.py)
2. 按需要填写启动模式后回车
3. 设置将会很快完成

## 修改密码

1. 编辑 [config.txt](config.txt) 将其中 key 值修改即可，密码长度不能超过32!
2. 只有当值被识别为json字符串时才有效，否则将被视为null，使用默认密码

## 卸载

1. 启动 [uninstallPython.cmd](uninstallPython.cmd) 卸载,按照提示进行操作
2. 卸载将会很快完成

___作者:azazo1___  
___邮箱:[azazo1@qq.com](azazo1@qq.com)___