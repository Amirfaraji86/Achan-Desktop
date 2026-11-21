# Achan | آچان

### Smart Network Connection Management for Windows

Achan is a lightweight and minimalist tool for managing network connectivity in Windows. It uses secure DNS, a local HTTP proxy, and a network tunnel.

All features are accessible through a Persian graphical user interface. The status of different network components is displayed step by step, allowing users to easily enable or disable the connection.

**Made with ❤️ by Faraj**

---

## ✨ Features

- Persian graphical user interface with right-to-left (RTL) layout.
- Enable and disable the connection using an animated toggle switch.
- Step-by-step status monitoring of the network engine, DNS, proxy, and tunnel.
- Support for DNS over HTTPS (DoH).
- Local HTTP proxy running at `127.0.0.1:4525`.
- TCP traffic routing through a TUN tunnel.
- Uses Wintun and `tun2proxy`.
- Diagnostic logging for troubleshooting network issues.
- Easy installation with no Python installation required on the target computer.
- Automatic and manual update checks for installed versions.
- Separate update channels for Windows 7 and Windows 10/11.

## 🖥️ Supported Operating Systems

| Operating System | Architecture | Release Channel |
|---|---|---|
| Windows 11 | x64 | Windows 10/11 |
| Windows 10 | x64 | Windows 10/11 |
| Windows 7 SP1 | x64 | Windows 7 |

The Windows 7 edition uses older, compatible versions of Python and networking dependencies.

Windows 7 and Python 3.8 are no longer receiving general public support. Using newer versions of Windows is recommended.

## ⚙️ How Does Achan Work?

Achan consists of several components that work together:

1. **Secure DNS:** DNS requests are sent through DNS over HTTPS to the `sky.rethinkdns.com` service.
2. **Local Proxy:** An HTTP proxy runs locally at `127.0.0.1:4525`.
3. **Network Tunnel:** The `tun2proxy` utility and Wintun driver are used to establish a TUN-based routing layer.
4. **Connection Management:** Achan monitors the status of network components and attempts to restore network settings and routes in a controlled manner when the connection is interrupted.

## 📥 Download and Installation

Visit the repository's Releases page to download the latest versions:

🔗 [Download Achan Releases](https://github.com/Amirfaraji86/Achan-Desktop/releases)

Choose the version compatible with your operating system:

- **Windows 10 & 11:** Edition designed for newer Windows versions.
- **Windows 7 SP1:** Edition compatible with Windows 7 Service Pack 1.

Three types of packages are provided for each platform:

| Package Type | Description |
|---|---|
| Setup | Standard Windows installer |
| Portable | Portable edition that requires no installation |
| Distribution | Complete package containing the main application files and documentation |

A platform-specific Manifest file is also provided to validate updates.

Administrator privileges are required to activate the network tunnel. Windows may display a User Account Control (UAC) prompt.

## 🔄 Automatic Updates

Installed versions of Achan include an AutoUpdater system.

This system periodically checks GitHub Releases for newer versions. Users can also manually check for updates from within the application.

The update process consists of the following steps:

1. Check for a new version in the appropriate stable release channel for the operating system.
2. Retrieve the platform-specific Manifest.
3. Download the appropriate installer.
4. Validate the file name, version, file size, and SHA-256 checksum.
5. Shut down the tunnel gracefully and close the application.
6. Launch the standalone updater.
7. Install the new version and restart Achan.

**Important Notes:**

- Windows may display a UAC prompt during the update installation process.
- Achan does not bypass Windows security prompts.
- The Portable edition is not automatically replaced and must be updated manually.
- Version 1.0.3 did not include an AutoUpdater system. Therefore, users of this version must manually install version 1.1.0 for their first upgrade. After that, installed versions can use automatic updates.

## ⚠️ Limitations and Transparency

Achan is not a VPN with a remote server and should not be confused with VPN services.

- **Does Not Hide Your Public IP:** Achan does not hide the user's public IP address.
- **UDP Limitation:** The HTTP proxy used by Achan does not support forwarding general UDP traffic.
- **Games and Voice Calls:** Online games, internet calls, and applications that depend on UDP may not work properly.
- **QUIC and HTTP/3:** Some applications and browsers may experience compatibility issues with these protocols.
- **Network Dependency:** Achan's performance depends on the ISP, network routing, and accessibility of the selected DoH service.
- **Network Recovery:** If the tunnel process is forcibly terminated or crashes unexpectedly, network routes may not be fully restored.

Access to specific websites or bypassing all internet restrictions is not guaranteed.

## 🪟 Windows 7 Requirements

The Windows 7 edition is specifically designed for Windows 7 SP1 x64.

Before installing the signed driver, the following Microsoft SHA-2 updates must be installed:

- KB4474419
- KB4490628

Windows must be restarted after installing these updates.

If necessary, the installer will also install the Visual C++ 2015–2019 Runtime.

## 🔐 Privacy and Logs

Application diagnostic logs are stored locally. Under normal operating conditions, Achan does not send these logs to any dedicated server.

Main log location:

```text
%LOCALAPPDATA%\Achan\logs\achan.log
```

The standalone updater also stores its logs in the same directory under the name `updater.log`.

Version information and installer files are retrieved from the official GitHub repository and its file hosting services for update checks and downloads.

Please note that DNS requests are sent to the selected DoH service for processing.

## 🧰 Technologies and Third-Party Projects

Achan uses the following tools and projects:

- [Python](https://www.python.org/)
- [Tkinter](https://docs.python.org/3/library/tkinter.html)
- [tun2proxy](https://github.com/tun2proxy/tun2proxy)
- [Wintun](https://www.wintun.net/)
- [Web Immortal Guards](https://github.com/mahdisml/WebImmortalGuards)
- [PyInstaller](https://pyinstaller.org/)
- [Inno Setup](https://jrsoftware.org/isinfo.php)

Licenses and notices for third-party libraries are available in the `THIRD_PARTY_NOTICES.md` file and the `licenses/` directory.

## 🏗️ Automated Build and Release Process

Achan builds are handled through GitHub Actions.

The project uses two main workflows:

| Workflow File | Operating System | Python Version |
|---|---|---|
| `build-windows.yml` | Windows 10/11 x64 | Python 3.13 |
| `build-windows7.yml` | Windows 7 SP1 x64 | Python 3.8.10 |

To publish a new version:

1. Make the required code changes.
2. Update the `RELEASE_NOTES_FA.md` file.
3. Synchronize the version number with the release script.
4. Run the following script from PowerShell in the repository root directory:

```powershell
.\scripts\publish-release.ps1 -Version X.Y.Z -CommitAndPush
```

This script synchronizes the application version information, Windows executable metadata, and Inno Setup configuration, then commits and pushes the changes.

After the push, both workflows detect the version change and, when a new version is identified:

- Build the application executables and installers.
- Prepare Portable and Distribution packages.
- Generate platform-specific Manifests.
- Create the corresponding Git tags and GitHub Releases for each platform.

Tag naming convention:

```text
vX.Y.Z-win10-11
vX.Y.Z-win7
```

**Important:** Do not create tags or releases manually, and do not upload release files separately. All release assets must be published through the GitHub Actions workflows.

A regular push that does not change the version number will not trigger the new-version release process.

## 🐛 Bug Reports and Suggestions

If you encounter an issue or have a suggestion for improving Achan, please use the repository's Issues section:

🔗 [Report a Bug or Submit a Suggestion](https://github.com/Amirfaraji86/Achan-Desktop/issues)

---

<div align="center">

### 🌿 Achan — Simple, Lightweight, and Practical

**Made by Faraj**

</div>
