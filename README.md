# Achan | آچان

### مدیریت هوشمند اتصال شبکه در ویندوز

Achan is a lightweight Windows desktop application that coordinates secure DNS-over-HTTPS, a local HTTP proxy, and a TUN interface through Wintun. The Persian-first interface reports each startup stage and provides controlled connection shutdown.

**Made by Faraj**

## Supported Windows editions

| Edition | Architecture | Build channel |
|---|---|---|
| Windows 11 | x64 | Windows 10/11 |
| Windows 10 | x64 | Windows 10/11 |
| Windows 7 SP1 | x64 | Windows 7 SP1 |

The Windows 7 build uses a separate, legacy-compatible Python and networking runtime. Windows 7 and Python 3.8 are end-of-life; a supported Windows release is recommended.

## Features

- Persian right-to-left desktop interface.
- Animated connection switch and explicit stage status for the engine, local proxy, secure DNS, and TUN tunnel.
- Local HTTP proxy bound to `127.0.0.1:4525`.
- DNS-over-HTTPS using `sky.rethinkdns.com`.
- Wintun and `tun2proxy` for system TCP routing.
- Local diagnostic logs.
- In-app update checks for installed Setup builds. A downloaded installer is validated against its platform manifest, byte size, and SHA-256 before the detached updater installs it and restarts Achan.
- Separate Windows 7 and Windows 10/11 release packages.

## Download and update

Open the repository's [Releases page](https://github.com/Amirfaraji86/Achan-Desktop/releases) and select the package matching your Windows edition. Each platform release provides a Setup installer, Portable archive, Distribution archive, and a platform-specific update manifest.

Installed Setup builds periodically check for a newer stable release and also provide a manual **Check for updates** action in the application. Windows may display a UAC confirmation because Achan's installer requires administrator privileges. Achan does not bypass Windows security prompts. Portable builds are not replaced in place by the updater.

**One-time migration:** version 1.0.3 did not include the updater. Users on 1.0.3 must manually install version 1.1.0 once; subsequent updates can be handled by the in-app updater.

## How Achan works

1. The application starts a local HTTP proxy.
2. DNS preflight uses DNS-over-HTTPS.
3. `tun2proxy` and Wintun create the TUN routing layer.
4. Achan monitors the tunnel process and attempts graceful route restoration on shutdown.

The proxy is local-only and does not provide a remote VPN relay. It does not hide the public IP address or relay arbitrary UDP traffic. Online games, voice calls, QUIC/HTTP3, and other UDP-dependent applications may not work as expected. Website availability is not guaranteed and depends on the network, ISP, and DoH service.

## Automated release process

The two workflows in `.github/workflows/` are:

- `build-windows.yml` — Windows 10/11 x64, Python 3.13.
- `build-windows7.yml` — Windows 7 SP1 x64, Python 3.8.10 and pinned compatible dependencies.

To publish a release, update the code and `RELEASE_NOTES_FA.md`, then run `scripts/publish-release.ps1 -Version X.Y.Z -CommitAndPush` in PowerShell from the repository root. The script synchronizes the Python, Windows version-resource, and Inno Setup versions, then commits and pushes to `main`. Both workflows detect the version change, build their packages, generate platform manifests, and create their own tags and GitHub Releases:

- `vX.Y.Z-win10-11`
- `vX.Y.Z-win7`

Do not create tags or releases manually and do not upload release assets in a separate step. A normal code push without a version change skips the build and release steps.

## Windows 7 prerequisites

The Windows 7 package targets Windows 7 SP1 x64. Microsoft SHA-2 updates KB4474419 and KB4490628 must be installed before the signed driver can be loaded, and Windows should be restarted afterward. The installer includes the Visual C++ 2015–2019 runtime when needed.

## Logs and privacy

Application logs are stored locally at:

```text
%LOCALAPPDATA%\Achan\logs\achan.log
```

Updater helper logs are stored in the same folder as `updater.log`. Achan does not send diagnostics to a dedicated Achan server. Update metadata and installer packages are requested from the official GitHub repository and its release-asset delivery hosts.

## Third-party components

- [Python](https://www.python.org/)
- [Tkinter](https://docs.python.org/3/library/tkinter.html)
- [tun2proxy](https://github.com/tun2proxy/tun2proxy)
- [Wintun](https://www.wintun.net/)
- [PyInstaller](https://pyinstaller.org/)
- [Inno Setup](https://jrsoftware.org/isinfo.php)

License notices are included in `THIRD_PARTY_NOTICES.md` and `licenses/`.

---

**Achan — Made by Faraj**
