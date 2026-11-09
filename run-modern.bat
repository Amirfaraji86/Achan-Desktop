@echo off
setlocal
cd /d "%~dp0"
python -u main_qt.py
if errorlevel 1 echo Achan exited with code %errorlevel%.
