if exist .\python-3.8.1-amd64.exe (goto start) else (goto download)
:start
mkdir python
rem python-3.8.1-amd64.exe /quiet TargetDir=%~dp0\python PrependPath=0 Shortcuts=0
call prepare.py
goto quit

:download
powershell -Command "$client = new-object System.Net.WebClient;$client.DownloadFile('https://www.python.org/ftp/python/3.8.1/python-3.8.1-amd64.exe','.\python-3.8.1-amd64.exe')"
goto start
:quit