[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repoRoot
try {
    foreach ($required in @(
        'main.py', 'main_qt.py', 'requirements-qt.txt', 'qt_ui\main.qml',
        '.github\workflows\build-windows.yml', 'scripts\publish-release.ps1'
    )) {
        if (-not (Test-Path (Join-Path $repoRoot $required))) {
            throw "Required release file was not found: $required. Extract the release overlay into the repository root first."
        }
    }

    # Keep the modern Qt entry point on the same version as the legacy entry point.
    $qtMainPath = Join-Path $repoRoot 'main_qt.py'
    $qtMain = [System.IO.File]::ReadAllText($qtMainPath, [System.Text.Encoding]::UTF8)
    $versionPattern = 'APP_VERSION\s*=\s*["''](?<version>\d+\.\d+\.\d+)["'']'
    if ([regex]::Matches($qtMain, $versionPattern).Count -ne 1) {
        throw 'Could not safely find exactly one APP_VERSION in main_qt.py.'
    }
    $qtMain = ([regex]::new($versionPattern)).Replace($qtMain, ('APP_VERSION = "' + $Version + '"'), 1)
    [System.IO.File]::WriteAllText($qtMainPath, $qtMain, [System.Text.UTF8Encoding]::new($false))

    # Qt 6.12 requires Windows 10 build 17763 (version 1809) or later.
    # The Win7 compiler defines Win7Build and keeps its own 6.1 SP1 minimum.
    $installerPath = Join-Path $repoRoot 'installer\Achan.iss'
    if (Test-Path $installerPath) {
        $installer = [System.IO.File]::ReadAllText($installerPath, [System.Text.Encoding]::UTF8)
        if ($installer -match '(?m)^MinVersion=10\.0$') {
            $installer = [regex]::Replace($installer, '(?m)^MinVersion=10\.0$', 'MinVersion=10.0.17763', 1)
            [System.IO.File]::WriteAllText($installerPath, $installer, [System.Text.UTF8Encoding]::new($false))
        } elseif ($installer -notmatch '(?m)^MinVersion=10\.0\.17763$') {
            throw 'Could not safely set the Windows 10/11 installer minimum version to build 17763.'
        }
    } else {
        throw 'installer/Achan.iss was not found.'
    }

    $workflowPath = Join-Path $repoRoot '.github\workflows\build-windows.yml'
    $workflow = [System.IO.File]::ReadAllText($workflowPath, [System.Text.Encoding]::UTF8)
    if ($workflow -match '(?m)^name: Build Achan - Windows 10 and 11\s*$' -and
        ([regex]::Matches($workflow, '(?m)^      - name: (?:Build self-contained Achan application|Build and validate modern Qt Quick Achan application)$')).Count -ne 1) {
        throw 'Windows 10/11 workflow does not contain exactly one recognized application build step.'
    }

    # Make the modern UI files part of the Windows 10/11 workflow trigger.
    if ($workflow -notmatch "(?m)^\s*- 'main_qt\.py'$") {
        $mainPathPattern = "(?m)^(\s*- 'main\.py')$"
        if ([regex]::Matches($workflow, $mainPathPattern).Count -ne 1) {
            throw 'Could not safely locate main.py in the Windows 10/11 workflow path filters.'
        }
        $workflow = ([regex]::new($mainPathPattern)).Replace(
            $workflow,
            ('$1' + "`r`n      - 'main_qt.py'" + "`r`n      - 'qt_ui/**'" + "`r`n      - 'tools/validate_qml.py'"),
            1
        )
    }

    $workflow = $workflow.Replace('cache-dependency-path: requirements.txt', 'cache-dependency-path: requirements-qt.txt')

    # Verify that the Qt entry point and version match the release version.
    $versionAnchor = '          $version = $Matches.version'
    if (-not $workflow.Contains($versionAnchor)) {
        throw 'The Windows 10/11 release-version block has changed; refusing to patch an unknown workflow layout.'
    }
    if ($workflow -notmatch 'main_qt\.py APP_VERSION') {
        $versionCheck = @'
          $qtSource = Get-Content 'main_qt.py' -Raw
          if ($qtSource -notmatch 'APP_VERSION\s*=\s*["''](?<qtVersion>\d+\.\d+\.\d+)["'']') {
            throw 'Could not read APP_VERSION from main_qt.py.'
          }
          if ($Matches.qtVersion -ne $version) {
            throw "main_qt.py APP_VERSION ($($Matches.qtVersion)) does not match the release version ($version)."
          }
'@
        $workflow = $workflow.Replace($versionAnchor, $versionAnchor + "`r`n" + $versionCheck.TrimEnd())
    }

    # Replace only the application-build step; the existing network runtime,
    # Inno Setup, manifest, artifact, and GitHub Release steps remain intact.
    $buildStepPattern = '(?ms)^      - name: (?:Build self-contained Achan application|Build and validate modern Qt Quick Achan application)\r?\n.*?(?=^      - name: Prepare Persian installer language)'
    if ([regex]::Matches($workflow, $buildStepPattern).Count -ne 1) {
        throw 'Could not find exactly one known Windows 10/11 application build step.'
    }

    $newBuildStep = @'
      - name: Build and validate modern Qt Quick Achan application
        if: steps.resolve.outputs.should_build == 'true'
        shell: pwsh
        run: |
          $ErrorActionPreference = 'Stop'
          python -m pip install --disable-pip-version-check -r requirements-qt.txt
          if ($LASTEXITCODE -ne 0) { throw 'Installing Qt build dependencies failed.' }
          python -c "import PySide6, shiboken6, dns.message, dns.rdatatype, requests; print('Qt Quick and networking dependencies: OK')"
          if ($LASTEXITCODE -ne 0) { throw 'Qt or networking dependency import failed.' }
          python -m compileall -q main_qt.py core tools/validate_qml.py
          if ($LASTEXITCODE -ne 0) { throw 'Python syntax validation failed.' }
          python -m unittest discover -s tests -v
          if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }
          python -m pip check
          if ($LASTEXITCODE -ne 0) { throw 'pip dependency consistency check failed.' }
          $env:QT_QPA_PLATFORM = 'offscreen'
          $env:QT_QUICK_BACKEND = 'software'
          python tools/validate_qml.py
          if ($LASTEXITCODE -ne 0) { throw 'Qt Quick QML smoke test failed.' }
          Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
          Remove-Item Env:QT_QUICK_BACKEND -ErrorAction SilentlyContinue

          python -m PyInstaller --noconfirm --clean --onedir --windowed --name Achan --icon assets/achan.ico --version-file version_info.txt --add-data "assets;assets" --add-data "qt_ui;qt_ui" --collect-all dns --collect-data certifi --hidden-import=dns.message --hidden-import=dns.rdatatype --hidden-import=PySide6.QtQuick --hidden-import=PySide6.QtQml --hidden-import=PySide6.QtQuickControls2 main_qt.py
          if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed to freeze the modern Qt Quick application.' }

          $app = Join-Path $env:GITHUB_WORKSPACE 'dist\Achan'
          if (-not (Test-Path (Join-Path $app 'Achan.exe'))) { throw 'Achan.exe was not produced.' }

          # Qt's deployment tool scans the QML imports and places the required
          # Qt DLLs, platform plugins, and Qt Quick modules beside the app.
          $pysideRoot = python -c "import pathlib, PySide6; print(pathlib.Path(PySide6.__file__).resolve().parent)"
          $windeployqt = Join-Path $pysideRoot 'Qt\bin\windeployqt.exe'
          if (-not (Test-Path $windeployqt)) { throw "windeployqt.exe was not found: $windeployqt" }
          & $windeployqt --qmldir (Join-Path $env:GITHUB_WORKSPACE 'qt_ui') --no-translations (Join-Path $app 'Achan.exe')
          if ($LASTEXITCODE -ne 0) { throw "windeployqt failed with exit code $LASTEXITCODE." }

          $qmlCandidates = @(
            (Join-Path $app 'qml\QtQuick'),
            (Join-Path $app '_internal\PySide6\Qt\qml\QtQuick'),
            (Join-Path $app 'PySide6\Qt\qml\QtQuick')
          )
          if (-not ($qmlCandidates | Where-Object { Test-Path $_ })) {
            throw 'Qt Quick QML import modules were not deployed beside Achan.exe.'
          }

          $bin = Join-Path $app 'bin'
          $licenses = Join-Path $app 'licenses'
          New-Item -ItemType Directory -Force -Path $bin, $licenses | Out-Null
          Copy-Item 'bin\tun2proxy-bin.exe' (Join-Path $bin 'tun2proxy-bin.exe') -Force
          Copy-Item 'bin\wintun.dll' (Join-Path $bin 'wintun.dll') -Force
          Copy-Item 'LICENSE-ORIGINAL-MIT.txt' (Join-Path $licenses 'WebImmortalGuards-MIT.txt') -Force
          Copy-Item 'licenses\*' $licenses -Force
          Copy-Item 'THIRD_PARTY_NOTICES.md' (Join-Path $app 'THIRD_PARTY_NOTICES.md') -Force
          python -m PyInstaller --noconfirm --clean --onefile --windowed --name AchanUpdater --workpath build\updater-work --distpath build\updater-dist --specpath build\updater-spec updater_helper.py
          if (-not (Test-Path 'build\updater-dist\AchanUpdater.exe')) { throw 'AchanUpdater.exe was not produced.' }
          Copy-Item 'build\updater-dist\AchanUpdater.exe' (Join-Path $app 'AchanUpdater.exe') -Force

'@
    $replacement = [System.Text.RegularExpressions.MatchEvaluator]{
        param($match)
        return $newBuildStep
    }
    $workflow = ([regex]::new($buildStepPattern)).Replace($workflow, $replacement, 1)
    [System.IO.File]::WriteAllText($workflowPath, $workflow, [System.Text.UTF8Encoding]::new($false))

    Write-Host "Modern Qt Quick release preparation completed for Achan $Version."
    Write-Host 'Windows 10/11 will build main_qt.py + qt_ui/main.qml.'
    Write-Host 'Windows 7 SP1 keeps the existing Tkinter build for compatibility.'
    Write-Host 'Next, review git diff, then run:'
    Write-Host ('.\scripts\publish-release.ps1 -Version ' + $Version + ' -CommitAndPush')
}
finally {
    Pop-Location
}
