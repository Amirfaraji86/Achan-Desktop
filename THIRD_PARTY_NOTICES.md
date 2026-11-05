# Third-party notices

Achan is a Windows desktop front end and local integration of the Web Immortal Guards networking approach. It is not an official build of the Android application.

- **Web Immortal Guards source** — original MIT-licensed source notice is retained in `licenses/WebImmortalGuards-MIT.txt`.
- **tun2proxy v0.8.7** — bundled from the official upstream Windows x64 release. The upstream project is MIT-licensed; its license is copied to `licenses/tun2proxy-MIT.txt` during the Windows build when available.
- **Wintun 0.14.1** — the official x64 DLL is bundled. The official archive's license/readme files are copied to `licenses/`; consult the Wintun terms at https://www.wintun.net/.
- **Inno Setup Farsi installer translation** — community translation from `jrsoftware/issrc` (Farsi.isl), pinned in the Windows build workflow; translator credit is retained in the translation file.
- **Microsoft Visual C++ Redistributable x64** — downloaded from Microsoft's official `aka.ms` distribution endpoint during the build. The Microsoft-signed installer is checked before bundling and is installed only when the runtime is absent.
- **Arabic Reshaper 3.1.0** — MIT-licensed Persian/Arabic glyph shaping library used by the Tk interface; its license is included in `licenses/arabic-reshaper-MIT.txt`.
- **python-bidi 0.6.12** — LGPL-3.0-licensed bidirectional text-layout library used for right-to-left Persian labels; its license is included in `licenses/python-bidi-LGPL-3.0.txt`.
- **Python, dnspython, requests, PyInstaller and Tcl/Tk** — the executable is produced with PyInstaller; the relevant package licenses remain with their bundled distributions and upstream projects.

The installer bundles application runtime components; users do not need a separate Python installation. Achan requires Windows 10/11 x64 and Administrator approval when the system tunnel is enabled.
