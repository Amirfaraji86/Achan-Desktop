[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [switch]$CommitAndPush,

    [string]$CommitMessage
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repoRoot
try {
    $branch = (git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') {
        throw "Run this script from the main branch. Current branch: '$branch'."
    }

    git remote get-url origin *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Git remote 'origin' is not configured."
    }

    $sourcePaths = @(
        (Join-Path $repoRoot 'main.py'),
        (Join-Path $repoRoot 'main_qt.py'),
        (Join-Path $repoRoot 'main_qt_win7.py')
    )
    $versionInfoPaths = @(
        (Join-Path $repoRoot 'version_info.txt'),
        (Join-Path $repoRoot 'version_info_win7.txt')
    )
    $notesPaths = @(
        (Join-Path $repoRoot 'RELEASE_NOTES_FA.md'),
        (Join-Path $repoRoot 'RELEASE_NOTES_WIN7_FA.md')
    )
    $statusPath = Join-Path $repoRoot 'PROJECT_STATUS.txt'
    $installerPath = Join-Path $repoRoot 'installer\Achan.iss'

    $appVersionPattern = 'APP_VERSION\s*=\s*["''](?<version>\d+\.\d+\.\d+)["'']'
    $currentVersions = @()
    foreach ($sourcePath in $sourcePaths) {
        $sourceText = [System.IO.File]::ReadAllText($sourcePath, [System.Text.Encoding]::UTF8)
        $appVersionMatches = [regex]::Matches($sourceText, $appVersionPattern)
        if ($appVersionMatches.Count -ne 1) {
            throw "Could not safely find exactly one APP_VERSION in $sourcePath."
        }
        $currentVersions += [version]$appVersionMatches[0].Groups['version'].Value
    }
    $currentVersion = ($currentVersions | Sort-Object -Descending | Select-Object -First 1)
    if ([version]$Version -le $currentVersion) {
        throw "New version must be greater than current version $currentVersion."
    }

    $newTuple = ($Version.Split('.') -join ', ') + ', 0'
    foreach ($sourcePath in $sourcePaths) {
        $sourceText = [System.IO.File]::ReadAllText($sourcePath, [System.Text.Encoding]::UTF8)
        $sourceText = ([regex]::new($appVersionPattern)).Replace(
            $sourceText,
            ('APP_VERSION = "' + $Version + '"'),
            1
        )
        [System.IO.File]::WriteAllText($sourcePath, $sourceText, [System.Text.UTF8Encoding]::new($false))
    }

    foreach ($versionInfoPath in $versionInfoPaths) {
        $versionInfo = [System.IO.File]::ReadAllText($versionInfoPath, [System.Text.Encoding]::UTF8)
        foreach ($field in @('filevers', 'prodvers')) {
            $pattern = "(?<prefix>$field\s*=\s*)\([0-9,\s]+\)"
            if ([regex]::Matches($versionInfo, $pattern).Count -ne 1) {
                throw "Could not safely update $field in $versionInfoPath."
            }
            $versionInfo = ([regex]::new($pattern)).Replace($versionInfo, ('$1(' + $newTuple + ')'), 1)
        }
        foreach ($field in @('FileVersion', 'ProductVersion')) {
            $pattern = "StringStruct\('$field',\s*'\d+\.\d+\.\d+'\)"
            if ([regex]::Matches($versionInfo, $pattern).Count -ne 1) {
                throw "Could not safely update $field in $versionInfoPath."
            }
            $versionInfo = ([regex]::new($pattern)).Replace(
                $versionInfo,
                ("StringStruct('$field', '$Version')"),
                1
            )
        }
        [System.IO.File]::WriteAllText($versionInfoPath, $versionInfo, [System.Text.UTF8Encoding]::new($false))
    }

    $installer = [System.IO.File]::ReadAllText($installerPath, [System.Text.Encoding]::UTF8)
    $installerPattern = '(?m)^  #define AppVersion "\d+\.\d+\.\d+"$'
    if ([regex]::Matches($installer, $installerPattern).Count -ne 1) {
        throw 'Could not safely update the fallback AppVersion in installer/Achan.iss.'
    }
    $installer = ([regex]::new($installerPattern)).Replace($installer, ('  #define AppVersion "' + $Version + '"'), 1)
    [System.IO.File]::WriteAllText($installerPath, $installer, [System.Text.UTF8Encoding]::new($false))

    foreach ($notesPath in $notesPaths) {
        if (-not (Test-Path $notesPath)) { continue }
        $notes = [System.IO.File]::ReadAllText($notesPath, [System.Text.Encoding]::UTF8)
        $notes = ([regex]::new('^# Achan \d+\.\d+\.\d+')).Replace($notes, ('# Achan ' + $Version), 1)
        [System.IO.File]::WriteAllText($notesPath, $notes, [System.Text.UTF8Encoding]::new($false))
    }
    if (Test-Path $statusPath) {
        $status = [System.IO.File]::ReadAllText($statusPath, [System.Text.Encoding]::UTF8)
        $status = ([regex]::new('^Achan \d+\.\d+\.\d+')).Replace($status, ('Achan ' + $Version), 1)
        [System.IO.File]::WriteAllText($statusPath, $status, [System.Text.UTF8Encoding]::new($false))
    }

    Write-Host "Achan version metadata updated: $currentVersion -> $Version"
    Write-Host 'Review RELEASE_NOTES_FA.md and inspect git diff before publishing.'

    if ($CommitAndPush) {
        if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
            $CommitMessage = "Release Achan $Version"
        }
        git add -A
        if ($LASTEXITCODE -ne 0) { throw 'git add failed.' }
        git diff --cached --quiet
        $diffExitCode = $LASTEXITCODE
        if ($diffExitCode -eq 0) { throw 'There are no staged changes to commit.' }
        if ($diffExitCode -ne 1) { throw "git diff failed with exit code $diffExitCode." }
        git commit -m $CommitMessage
        if ($LASTEXITCODE -ne 0) { throw 'git commit failed.' }
        git push origin main
        if ($LASTEXITCODE -ne 0) {
            throw 'Push failed. The version commit is local; review git status and retry: git push origin main.'
        }
        Write-Host 'Push completed. GitHub Actions will build both platforms and create the tags/releases automatically.'
    }
}
finally {
    Pop-Location
}
