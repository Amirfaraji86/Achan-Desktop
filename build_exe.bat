@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

echo [1/5] Checking the build interpreter...
%PY% --version
if errorlevel 1 goto :error

echo [2/5] Installing build dependencies...
%PY% -m pip install --disable-pip-version-check --retries 4 --timeout 30 -r requirements.txt pyinstaller
if errorlevel 1 goto :error
%PY% -c "import dns.message, dns.rdatatype, requests, certifi, arabic_reshaper; from bidi.algorithm import get_display; print('Runtime imports: OK')"
if errorlevel 1 goto :error

if not exist "bin\tun2proxy-bin.exe" goto :missing_bin
if not exist "bin\wintun.dll" goto :missing_bin

echo [3/5] Building self-contained Achan application folder...
%PY% -m PyInstaller --noconfirm --clean --onedir --windowed --name Achan --icon "assets\achan.ico" --version-file "version_info.txt" --add-data "assets;assets" --collect-all dns --collect-all arabic_reshaper --collect-all bidi --collect-data certifi --hidden-import=dns.message --hidden-import=dns.rdatatype --hidden-import=bidi.algorithm main.py
if errorlevel 1 goto :error

if not exist "dist\Achan\bin" mkdir "dist\Achan\bin"
copy /y "bin\tun2proxy-bin.exe" "dist\Achan\bin\tun2proxy-bin.exe" >nul
copy /y "bin\wintun.dll" "dist\Achan\bin\wintun.dll" >nul
if not exist "dist\Achan\licenses" mkdir "dist\Achan\licenses"
copy /y "LICENSE-ORIGINAL-MIT.txt" "dist\Achan\licenses\LICENSE-ORIGINAL-MIT.txt" >nul
copy /y "licenses\*" "dist\Achan\licenses\" >nul 2>nul
copy /y "THIRD_PARTY_NOTICES.md" "dist\Achan\THIRD_PARTY_NOTICES.md" >nul

echo [4/5] Application build complete: dist\Achan\Achan.exe
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
  if not exist "build\vc_redist.x64.exe" goto :cloud_installer
  if not exist "installer\Farsi.isl" goto :cloud_installer
  echo [5/5] Compiling the installer...
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DAppVersion=1.0.0 "installer\Achan.iss"
  if errorlevel 1 goto :error
  echo Installer created in dist\Achan-Setup-1.0.0.exe
) else (
  echo Inno Setup 6 is not installed. The app folder is ready, but Setup.exe was not built.
  echo Use the GitHub Actions workflow to build the installer in the cloud.
)

echo.
echo Done. Target PCs do not need Python installed.
pause
exit /b 0

:cloud_installer
echo The local build is ready, but installer inputs are missing.
echo Use the GitHub Actions workflow to generate the complete Setup.exe package in the cloud.
exit /b 0

:missing_bin
echo Required signed runtime files are missing.
echo Run INSTALL_TUN2PROXY.bat first, or use the cloud workflow.
pause
exit /b 2

:error
echo Build failed. See the first error above.
pause
exit /b 1
