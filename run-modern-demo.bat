@echo off
setlocal
cd /d "%~dp0"
python -u main_qt.py --demo
if errorlevel 1 echo Achan exited with code %errorlevel%.
