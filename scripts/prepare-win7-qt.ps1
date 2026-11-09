[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version = '1.2.1'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repoRoot

function Replace-ExactOnce {
    param(
        [string]$Text,
        [string]$Old,
        [string]$New,
        [string]$Label
    )
    $count = ([regex]::Matches($Text, [regex]::Escape($Old))).Count
    if ($count -ne 1) {
        throw "Expected exactly one occurrence of '$Label'; found $count. No safe automatic replacement was made."
    }
    return $Text.Replace($Old, $New)
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

try {
    $requiredFiles = @(
        'main_qt.py',
        'qt_ui\main.qml',
        'tools\validate_qml.py',
        'version_info.txt',
        '.github\workflows\build-windows7.yml',
        'installer\Achan.iss',
        'scripts\publish-release.ps1'
    )
    foreach ($relativePath in $requiredFiles) {
        if (-not (Test-Path (Join-Path $repoRoot $relativePath))) {
            throw "Required source file is missing: $relativePath"
        }
    }

    # 1) Clone the already-tested modern bridge. This creates a Win7-only copy;
    #    main_qt.py and the Windows 10/11 workflow are never edited.
    $qtMain = [System.IO.File]::ReadAllText((Join-Path $repoRoot 'main_qt.py'), [System.Text.Encoding]::UTF8).Replace("`r`n", "`n")
    if ($qtMain -notmatch 'from __future__ import annotations') {
        throw 'main_qt.py no longer has postponed annotations; check Python 3.8 compatibility manually.'
    }
    if (([regex]::Matches($qtMain, 'from PySide6\.')).Count -lt 4) {
        throw 'Could not locate the expected PySide6 imports in main_qt.py.'
    }
    $qtMain = $qtMain.Replace('from PySide6.', 'from PySide2.')
    $qtMain = Replace-ExactOnce $qtMain 'from PySide2.QtCore import QObject, Property, QSettings, QTimer, QUrl, Signal, Slot' 'from PySide2.QtCore import QObject, Property, QSettings, QTimer, QUrl, Qt, Signal, Slot' 'Qt 5 window edge enum import'

    $versionPattern = 'APP_VERSION\s*=\s*["'']\d+\.\d+\.\d+["'']'
    if (([regex]::Matches($qtMain, $versionPattern)).Count -ne 1) {
        throw 'Could not safely identify exactly one APP_VERSION in main_qt.py.'
    }
    $qtMain = ([regex]::new($versionPattern)).Replace($qtMain, ('APP_VERSION = "' + $Version + '"'), 1)

    $qtMain = Replace-ExactOnce $qtMain 'return "Windows 10/11 x64"' 'return "Windows 7 SP1 x64"' 'update channel label'

    $oldWindowsGuard = @'
        win_version = sys.getwindowsversion()
        if win_version.major < 10:
            print("The modern Qt interface requires Windows 10 or Windows 11. Use the legacy Windows 7 build.")
            return 2
        if win_version.major == 10 and getattr(win_version, "build", 0) < 17763:
            print("The modern Qt interface requires Windows 10 version 1809 (build 17763) or later.")
            return 2
'@
    $newWindowsGuard = @'
        win_version = sys.getwindowsversion()
        if (win_version.major, win_version.minor) != (6, 1):
            print("This Achan edition is intended for Windows 7 SP1 x64.")
            return 2
        if getattr(win_version, "service_pack_major", 0) < 1:
            print("Windows 7 Service Pack 1 is required.")
            return 2
'@
    $qtMain = Replace-ExactOnce $qtMain $oldWindowsGuard $newWindowsGuard 'Windows 10-only guard block'

    $oldImportPaths = @'
    qml_import_candidates = (
        APP_DIR / "qml",
        resource_path("qml"),
        resource_path("PySide6/Qt/qml"),
        APP_DIR / "PySide6" / "Qt" / "qml",
    )
'@
    $newImportPaths = @'
    qml_import_candidates = (
        APP_DIR / "qml",
        resource_path("qml"),
        resource_path("PySide2/qml"),
        APP_DIR / "PySide2" / "qml",
    )
'@
    $qtMain = Replace-ExactOnce $qtMain $oldImportPaths $newImportPaths 'PySide6 QML import paths'
    $qtMain = Replace-ExactOnce $qtMain 'resource_path("qt_ui/main.qml")' 'resource_path("qt_ui_win7/main.qml")' 'Win7 QML entry path'
    $qtMain = Replace-ExactOnce $qtMain 'return app.exec()' 'return app.exec_()' 'Qt 5 event-loop method'
    $newMutexInit = '        self.mutex = mutex' + "`n" + '        self._main_window = None'
    $qtMain = Replace-ExactOnce $qtMain '        self.mutex = mutex' $newMutexInit 'Win7 native window handle'
    $windowMethods = @'
    def set_main_window(self, window: QQuickWindow) -> None:
        self._main_window = window

    @Slot()
    def startSystemMove(self) -> None:
        # Qt 5.15 exposes native move/resize on QWindow, but not through the
        # QtQuick.Window QML wrapper. Route those calls through this bridge.
        if self._main_window is not None:
            self._main_window.startSystemMove()

    @Slot(int)
    def startSystemResize(self, edge: int) -> None:
        if self._main_window is None:
            return
        edge_map = {
            int(Qt.LeftEdge): Qt.LeftEdge,
            int(Qt.RightEdge): Qt.RightEdge,
            int(Qt.TopEdge): Qt.TopEdge,
            int(Qt.BottomEdge): Qt.BottomEdge,
        }
        selected_edge = edge_map.get(int(edge))
        if selected_edge is not None:
            self._main_window.startSystemResize(selected_edge)

    def _log(self, message: str, *args) -> None:
'@
    $qtMain = Replace-ExactOnce $qtMain '    def _log(self, message: str, *args) -> None:' $windowMethods 'Qt 5 native window bridge methods'
    $newWindowAttach = '    bridge.set_main_window(main_window)' + "`n`n" + '    main_window.show()'
    $qtMain = Replace-ExactOnce $qtMain '    main_window.show()' $newWindowAttach 'attach the QQuickWindow to the Win7 bridge'
    $qtMain = $qtMain.Replace('Achan modern Qt Quick interface', 'Achan Qt Quick interface for Windows 7')
    # WIN7-PYSIDE2-CONSTANT-PROPERTY-FIX
    # PySide2 5.15 is more reliable when constant properties use fget syntax.
    $oldConstantProperties = @'
    @Property(str, constant=True)
    def version(self) -> str:
        return APP_VERSION

    @Property(bool, constant=True)
    def demoMode(self) -> bool:
        return self.demo
'@
    $newConstantProperties = @'
    def _get_version(self) -> str:
        return APP_VERSION

    version = Property(str, fget=_get_version, constant=True)

    def _get_demo_mode(self) -> bool:
        return self.demo

    demoMode = Property(bool, fget=_get_demo_mode, constant=True)
'@
    $qtMain = Replace-ExactOnce $qtMain $oldConstantProperties $newConstantProperties 'PySide2 constant version/demo properties'

    $oldUpdateChannelProperty = @'
    @Property(str, constant=True)
    def updateChannel(self) -> str:
        return "Windows 7 SP1 x64"
'@
    $newUpdateChannelProperty = @'
    def _get_update_channel(self) -> str:
        return "Windows 7 SP1 x64"

    updateChannel = Property(str, fget=_get_update_channel, constant=True)
'@
    $qtMain = Replace-ExactOnce $qtMain $oldUpdateChannelProperty $newUpdateChannelProperty 'PySide2 constant updateChannel property'

    Write-Utf8NoBom (Join-Path $repoRoot 'main_qt_win7.py') $qtMain

    # 2) Clone the exact QML design and only lower the imports to Qt 5.15.
    $qml = [System.IO.File]::ReadAllText((Join-Path $repoRoot 'qt_ui\main.qml'), [System.Text.Encoding]::UTF8).Replace("`r`n", "`n")
    $qml = Replace-ExactOnce $qml 'import QtQuick 6.8' 'import QtQuick 2.15' 'QtQuick version import'
    $qml = Replace-ExactOnce $qml 'import QtQuick.Controls 6.8' 'import QtQuick.Controls 2.15' 'Qt Quick Controls version import'
    $qml = Replace-ExactOnce $qml 'import QtQuick.Layouts 6.8' 'import QtQuick.Layouts 1.15' 'Qt Quick Layouts version import'
    $qml = Replace-ExactOnce $qml 'window.startSystemMove()' 'bridge.startSystemMove()' 'Qt 5 native window move bridge'
    if (([regex]::Matches($qml, 'window\.startSystemResize\(')).Count -ne 4) { throw 'Expected four QML resize hit regions.' }
    $qml = $qml.Replace('window.startSystemResize(', 'bridge.startSystemResize(')
    if ($qml -notmatch '(?m)^import QtQuick\.Window 2\.15$') {
        $qml = $qml.Replace("import QtQuick.Layouts 1.15`r`n", "import QtQuick.Layouts 1.15`r`nimport QtQuick.Window 2.15`r`n")
        if ($qml -notmatch '(?m)^import QtQuick\.Window 2\.15$') {
            $qml = $qml.Replace("import QtQuick.Layouts 1.15`n", "import QtQuick.Layouts 1.15`nimport QtQuick.Window 2.15`n")
        }
    }
    if ($qml -match 'import QtQuick(?:\.Controls|\.Layouts)? 6\.') {
        throw 'A Qt 6 QML import remains in the Windows 7 QML copy.'
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot 'qt_ui_win7') | Out-Null
    Write-Utf8NoBom (Join-Path $repoRoot 'qt_ui_win7\main.qml') $qml

    # 3) Make a Qt 5 / PySide2 QML smoke test by cloning the proven Win10 test.
    $validator = [System.IO.File]::ReadAllText((Join-Path $repoRoot 'tools\validate_qml.py'), [System.Text.Encoding]::UTF8).Replace("`r`n", "`n")
    $validator = $validator.Replace('PySide6', 'PySide2')
    $validator = Replace-ExactOnce $validator 'from main_qt import AchanBridge, SingleInstance' 'from main_qt_win7 import AchanBridge, SingleInstance' 'Win7 bridge import'
    $validator = Replace-ExactOnce $validator 'PROJECT_ROOT / "qt_ui" / "main.qml"' 'PROJECT_ROOT / "qt_ui_win7" / "main.qml"' 'Win7 QML test path'
    $validator = $validator.Replace('QEvent.Type.DeferredDelete', 'QEvent.DeferredDelete')
    $validator = $validator.Replace('app.exec()', 'app.exec_()')
    New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot 'tools') | Out-Null
    Write-Utf8NoBom (Join-Path $repoRoot 'tools\validate_qml_win7.py') $validator

    # 4) Dedicated, pinned Win7/Python 3.8 dependency set; Win10 requirements are untouched.
    $requirements = @'
# Windows 7 SP1 x64 modern UI: Qt 5.15 / PySide2 on Python 3.8.10.
PySide2==5.15.2.1
shiboken2==5.15.2.1
dnspython==2.6.1
requests==2.32.3
urllib3==2.2.3
charset-normalizer==3.3.2
idna==3.10
certifi==2026.10.23
arabic-reshaper==3.0.0
python-bidi==0.5.2
PyInstaller==5.13.2
'@
    Write-Utf8NoBom (Join-Path $repoRoot 'requirements-win7-qt.txt') $requirements

    # 5) Separate Win7 version metadata so the already-published Win10 1.2.0
    #    release and its version_info.txt remain unchanged.
    $versionInfo = [System.IO.File]::ReadAllText((Join-Path $repoRoot 'version_info.txt'), [System.Text.Encoding]::UTF8).Replace("`r`n", "`n")
    if (-not $versionInfo.Contains('1.2.0')) {
        throw 'The source version_info.txt is not the expected 1.2.0 base; refusing to guess the Win7 file version.'
    }
    $versionInfo = $versionInfo.Replace('1.2.0', $Version).Replace('1, 2, 0, 0', (($Version.Split('.')[0]) + ', ' + ($Version.Split('.')[1]) + ', ' + ($Version.Split('.')[2]) + ', 0'))
    Write-Utf8NoBom (Join-Path $repoRoot 'version_info_win7.txt') $versionInfo

    $releaseNotes = @"
# Achan $Version — رابط Qt Quick مدرن برای Windows 7 SP1

## رابط کاربری
- رابط Qt Quick با همان چیدمان، رنگ‌بندی، پنل‌ها و انیمیشن‌های نسخه مدرن Windows 10/11.
- پشتیبانی فارسی و انگلیسی و ذخیره زبان انتخاب‌شده.
- نوار عنوان اختصاصی، کنترل پنجره، دکمه اتصال با وضعیت‌های قرمز/زرد/سبز.
- پنل‌های تنظیمات، به‌روزرسانی، درباره آچان و گزارش فنی.
- افکت‌های Fade، Glow، Neon Border، ذرات پس‌زمینه و انیمیشن دکمه‌ها.

## سازگاری
- Windows 7 SP1 x64 با Python runtime داخلی مبتنی بر Python 3.8.
- Qt 5.15.2 و PySide2 5.15.2.1 برای پشتیبانی از Windows 7.
- رابط Windows 10/11 و فایل‌های ساخت آن در این تغییر دست‌نخورده می‌مانند.

## هسته شبکه و به‌روزرسانی
- حفظ NetworkController، Wintun، tun2proxy و پراکسی محلی آچان.
- حفظ کانال به‌روزرسانی مستقل Windows 7 SP1 و اعتبارسنجی اندازه و SHA-256 نصب‌کننده.
"@
    Write-Utf8NoBom (Join-Path $repoRoot 'RELEASE_NOTES_WIN7_FA.md') $releaseNotes

    # 6) Move only the Win7 workflow to the Qt 5.15 build. Do not edit the
    #    Windows 10/11 workflow, main_qt.py, qt_ui/main.qml, or Win10 metadata.
    $workflowPath = Join-Path $repoRoot '.github\workflows\build-windows7.yml'
    $workflow = [System.IO.File]::ReadAllText($workflowPath, [System.Text.Encoding]::UTF8).Replace("`r`n", "`n")

    if ($workflow -notmatch "(?m)^\s*- 'main_qt_win7\.py'$" ) {
        $pathFilterReplacement = @'
      - 'main.py'
      - 'main_qt_win7.py'
      - 'qt_ui_win7/**'
      - 'tools/validate_qml_win7.py'
      - 'requirements-win7-qt.txt'
      - 'version_info_win7.txt'
      - 'RELEASE_NOTES_WIN7_FA.md'
'@
        $workflow = Replace-ExactOnce $workflow "      - 'main.py'" $pathFilterReplacement 'Win7 workflow path filters'
    }

    $workflow = Replace-ExactOnce $workflow "Get-Content 'main.py' -Raw" "Get-Content 'main_qt_win7.py' -Raw" 'Win7 version source'
    $workflow = Replace-ExactOnce $workflow "Get-Content 'version_info.txt' -Raw" "Get-Content 'version_info_win7.txt' -Raw" 'Win7 version resource file'
    $workflow = Replace-ExactOnce $workflow '"$($env:EVENT_BEFORE):main.py"' '"$($env:EVENT_BEFORE):main_qt_win7.py"' 'Win7 previous-version source'
    $workflow = Replace-ExactOnce $workflow 'cache-dependency-path: requirements-win7.txt' 'cache-dependency-path: requirements-win7-qt.txt' 'Win7 pip cache dependency'
    $workflow = $workflow.Replace("Get-Content 'RELEASE_NOTES_FA.md' -Raw", "Get-Content 'RELEASE_NOTES_WIN7_FA.md' -Raw")

    $buildStepPattern = '(?ms)^      - name: (?:Build with Windows 7-compatible Python and PyInstaller|Build modern Qt Quick Achan for Windows 7 \(PySide2 / Qt 5\.15\))\r?\n.*?(?=^      - name: Prepare Persian installer language)'
    if (([regex]::Matches($workflow, $buildStepPattern)).Count -ne 1) {
        throw 'Could not find exactly one known Win7 application build step. Review build-windows7.yml before retrying.'
    }

    $newBuildStep = @'
      - name: Build modern Qt Quick Achan for Windows 7 (PySide2 / Qt 5.15)
        if: steps.resolve.outputs.should_build == 'true'
        shell: pwsh
        run: |
          $ErrorActionPreference = 'Stop'
          python -m pip install --disable-pip-version-check 'pip==24.3.1'
          if ($LASTEXITCODE -ne 0) { throw 'Pinning a Python 3.8-compatible pip failed.' }
          python -m pip install --disable-pip-version-check -r requirements-win7-qt.txt
          if ($LASTEXITCODE -ne 0) { throw 'Installing Win7 Qt dependencies failed.' }
          python -c "import PySide2, shiboken2, dns.message, dns.rdatatype, requests; print('Win7 Qt Quick and networking dependencies: OK')"
          if ($LASTEXITCODE -ne 0) { throw 'Win7 Qt or networking dependency import failed.' }
          python -m compileall -q main_qt_win7.py core tools/validate_qml_win7.py
          if ($LASTEXITCODE -ne 0) { throw 'Win7 Python syntax validation failed.' }
          python -m unittest discover -s tests -v
          if ($LASTEXITCODE -ne 0) { throw 'Win7 unit tests failed.' }
          python -m pip check
          if ($LASTEXITCODE -ne 0) { throw 'Win7 pip dependency consistency check failed.' }
          $env:QT_QPA_PLATFORM = 'offscreen'
          $env:QT_QUICK_BACKEND = 'software'
          python tools/validate_qml_win7.py
          if ($LASTEXITCODE -ne 0) { throw 'Win7 Qt Quick QML smoke test failed.' }
          Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
          Remove-Item Env:QT_QUICK_BACKEND -ErrorAction SilentlyContinue

          python -m PyInstaller --noconfirm --clean --onedir --windowed --name Achan --icon assets/achan.ico --version-file version_info_win7.txt --add-data "assets;assets" --add-data "qt_ui_win7;qt_ui_win7" --collect-all PySide2 --collect-all shiboken2 --collect-all dns --collect-all arabic_reshaper --collect-all bidi --collect-data certifi --hidden-import=PySide2.QtQuick --hidden-import=PySide2.QtQml --hidden-import=PySide2.QtQuickControls2 --hidden-import=dns.message --hidden-import=dns.rdatatype --hidden-import=bidi.algorithm main_qt_win7.py
          if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed to freeze the Windows 7 Qt Quick application.' }

          $app = Join-Path $env:GITHUB_WORKSPACE 'dist\Achan'
          if (-not (Test-Path (Join-Path $app 'Achan.exe'))) { throw 'Win7 Achan.exe was not produced.' }

          # PyInstaller's PySide2 hook collects Qt binaries. Copy Qt 5.15 QML
          # import modules explicitly so the Win7 QML engine can resolve Controls.
          $pyside2Root = python -c "import pathlib, PySide2; print(pathlib.Path(PySide2.__file__).resolve().parent)"
          $qmlSource = Join-Path $pyside2Root 'qml'
          if (-not (Test-Path (Join-Path $qmlSource 'QtQuick'))) { throw "PySide2 QtQuick QML modules were not found: $qmlSource" }
          $qmlDestination = Join-Path $app 'PySide2\qml'
          New-Item -ItemType Directory -Force -Path $qmlDestination | Out-Null
          Copy-Item -Path (Join-Path $qmlSource '*') -Destination $qmlDestination -Recurse -Force
          if (-not (Test-Path (Join-Path $qmlDestination 'QtQuick\Controls.2'))) { throw 'Qt Quick Controls 2 QML modules were not bundled for Win7.' }

          $qwindowsPlugin = Get-ChildItem -Path $app -Recurse -File -Filter 'qwindows.dll' | Select-Object -First 1
          if (-not $qwindowsPlugin) { throw 'The Qt Windows platform plugin (qwindows.dll) was not bundled.' }

          $bin = Join-Path $app 'bin'
          $licenses = Join-Path $app 'licenses'
          New-Item -ItemType Directory -Force -Path $bin, $licenses | Out-Null
          Copy-Item 'bin\tun2proxy-bin.exe' (Join-Path $bin 'tun2proxy-bin.exe') -Force
          Copy-Item 'bin\wintun.dll' (Join-Path $bin 'wintun.dll') -Force
          Copy-Item 'LICENSE-ORIGINAL-MIT.txt' (Join-Path $licenses 'WebImmortalGuards-MIT.txt') -Force
          Copy-Item 'licenses\*' $licenses -Force
          Copy-Item 'THIRD_PARTY_NOTICES.md' (Join-Path $app 'THIRD_PARTY_NOTICES.md') -Force
          python -m PyInstaller --noconfirm --clean --onefile --windowed --name AchanUpdater --workpath build\updater-work --distpath build\updater-dist --specpath build\updater-spec updater_helper.py
          if ($LASTEXITCODE -ne 0) { throw 'Building the Win7 updater helper failed.' }
          if (-not (Test-Path 'build\updater-dist\AchanUpdater.exe')) { throw 'AchanUpdater.exe was not produced.' }
          Copy-Item 'build\updater-dist\AchanUpdater.exe' (Join-Path $app 'AchanUpdater.exe') -Force

'@
    $workflow = ([regex]::new($buildStepPattern)).Replace(
        $workflow,
        [System.Text.RegularExpressions.MatchEvaluator]{ param($match) return $newBuildStep },
        1
    )

    # Refuse accidental cross-channel edits and verify the new version/tag wiring.
    if ($workflow -notmatch 'Get-Content ''main_qt_win7\.py'' -Raw' -or
        $workflow -notmatch 'Get-Content ''version_info_win7\.txt'' -Raw' -or
        $workflow -notmatch 'main_qt_win7\.py' -or
        $workflow -notmatch 'requirements-win7-qt\.txt' -or
        $workflow -notmatch 'main_qt_win7\.py') {
        throw 'The Win7 workflow did not pass its post-patch consistency checks.'
    }
    $buildSection = [regex]::Match($workflow, $buildStepPattern).Value
    if (-not $buildSection) {
        throw 'The patched Win7 build step could not be re-read for verification.'
    }
    if ($buildSection -match 'PySide6|main_qt\.py|qt_ui/main\.qml') {
        throw 'The new Win7 build section still references the Win10 Qt 6 application.'
    }

    Write-Utf8NoBom $workflowPath $workflow

    Write-Host "Prepared Achan $Version for Windows 7 SP1 using Qt 5.15 / PySide2."
    Write-Host 'Created: main_qt_win7.py, qt_ui_win7, requirements-win7-qt.txt, version_info_win7.txt, tools/validate_qml_win7.py, RELEASE_NOTES_WIN7_FA.md.'
    Write-Host 'Modified only: .github/workflows/build-windows7.yml.'
    Write-Host 'Windows 10/11 source, QML, dependencies, workflow, and version metadata were not modified.'
    Write-Host 'Next: inspect git status and git diff; do not publish until the Win7 Actions build passes.'
}
finally {
    Pop-Location
}
