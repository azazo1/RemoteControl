# coding=utf-8
import os
import sys

needs = ['pip', 'pygame', 'pyperclip', 'psutil', 'pynput', 'pycryptodome', 'pywin32',
         'opencv-python', 'Pillow']
logName = 'Azazo1Logs.txt'
print('Start')
state = 1
for p in sys.path:
    for module in needs:
        print(f'Installing:{module}')
        if not os.path.isdir(p):
            continue
        os.chdir(p)
        state = (os.system(f'python -m '
                           f'pip install {module} --upgrade '
                           f'-i https://pypi.douban.com/simple --no-warn-script-location'
                           f'>>{logName}')
                 and state)
    if state == 0:  # 成功安装
        break
with open(logName, 'rb') as r:
    print(r.read().decode())
print('Over')
os.system('pause')
