# Third-party notices

Achan is a Windows desktop front end and local integration of the Web Immortal Guards networking approach. It is not an official build of the Android application.

- **Web Immortal Guards source** — original MIT-licensed source notice is retained in `licenses/WebImmortalGuards-MIT.txt`.
- **tun2proxy v0.8.7** — the Windows 10/11 build uses the official x64 MSVC target; the Windows 7 build uses the dedicated `x86_64-win7-windows-msvc` target. The upstream project is MIT-licensed; its license is copied to `licenses/tun2proxy-MIT.txt` during the Windows build.
- **Wintun 0.14.1** — the official x64 DLL is bundled. The upstream Wintun project documents support for Windows 7, 8, 8.1 and 10; the official archive's license/readme files are copied to `licenses/`.
- **Inno Setup Farsi installer translation** — community translation from `jrsoftware/issrc` (Farsi.isl), pinned in the Windows build workflow; translator credit is retained in the translation file.
- **Microsoft Visual C++ Redistributable x64** — the Windows 10/11 package uses the current Microsoft distribution; the Windows 7 package uses the Visual Studio 2019 14.29 runtime line. Microsoft signatures are checked before bundling.
- **Arabic Reshaper** — the modern build uses 3.1.0; the Windows 7 build pins 3.0.0 for Python 3.8 compatibility. MIT license files are included in `licenses/`.
- **python-bidi** — the modern build uses 0.6.12; the Windows 7 build pins 0.5.2 for Python 3.8 compatibility. LGPL-3.0 license files are included in `licenses/`.
- **Python, dnspython, requests, PyInstaller and Tcl/Tk** — the executable is produced with PyInstaller; the relevant package licenses remain with their bundled distributions and upstream projects.

The installers bundle the application runtime; users do not need a separate Python installation. All builds require Administrator approval when the system tunnel is enabled. The Windows 7 build specifically targets Windows 7 SP1 x64.
