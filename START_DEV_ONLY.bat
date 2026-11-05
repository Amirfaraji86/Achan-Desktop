@echo off
setlocal
cd /d "%~dp0"
echo This launcher is for source-code development only.
echo End users should install and run Achan-Setup.exe or Achan.exe.
where py >nul 2>nul
if %errorlevel%==0 (py -3 main.py) else (python main.py)
if errorlevel 1 pause
