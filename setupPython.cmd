rem todo 需要安装包
mkdir python
python-3.8.1-amd64.exe /quiet TargetDir=%~dp0\python PrependPath=0 Shortcuts=0
call prepare.py