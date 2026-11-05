$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root = Split-Path -Parent $PSScriptRoot
$Bin = Join-Path $Root 'bin'
$Temp = Join-Path $env:TEMP 'achan-deps'
New-Item -ItemType Directory -Force -Path $Bin, $Temp | Out-Null

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'Achan targets 64-bit Windows 10/11.'
}

# Pinned upstream release. SHA-256 is checked before extraction.
$TunUrl = 'https://github.com/tun2proxy/tun2proxy/releases/download/v0.8.7/tun2proxy-x86_64-pc-windows-msvc.zip'
$TunHash = '801396ff46776aac4d9a6660a2972dbeb70b68c90a95a38289126c756298f863'
$TunZip = Join-Path $Temp 'tun2proxy-win64.zip'
Invoke-WebRequest -Uri $TunUrl -OutFile $TunZip
$ActualTunHash = (Get-FileHash -Algorithm SHA256 $TunZip).Hash.ToLowerInvariant()
if ($ActualTunHash -ne $TunHash) {
    throw "tun2proxy SHA-256 mismatch. Expected $TunHash, received $ActualTunHash"
}

$TunExtract = Join-Path $Temp 'tun2proxy-extracted'
if (Test-Path $TunExtract) { Remove-Item $TunExtract -Recurse -Force }
Expand-Archive -Path $TunZip -DestinationPath $TunExtract -Force
$TunExe = Get-ChildItem -Path $TunExtract -Filter '*.exe' -Recurse |
    Where-Object { $_.Name -match '^tun2proxy(-bin)?\.exe$' } |
    Select-Object -First 1
if (-not $TunExe) {
    $TunExe = Get-ChildItem -Path $TunExtract -Filter '*tun2proxy*.exe' -Recurse | Select-Object -First 1
}
if (-not $TunExe) { throw 'Could not find the tun2proxy executable in the official release archive.' }
Copy-Item $TunExe.FullName (Join-Path $Bin 'tun2proxy-bin.exe') -Force

# Wintun DLL, required by tun2proxy on Windows. Verify official archive hash.
$WintunUrl = 'https://www.wintun.net/builds/wintun-0.14.1.zip'
$WintunHash = '07c256185d6ee3652e09fa55c0b673e2624b565e02c4b9091c79ca7d2f24ef51'
$WintunZip = Join-Path $Temp 'wintun-0.14.1.zip'
Invoke-WebRequest -Uri $WintunUrl -OutFile $WintunZip
$ActualWintunHash = (Get-FileHash -Algorithm SHA256 $WintunZip).Hash.ToLowerInvariant()
if ($ActualWintunHash -ne $WintunHash) {
    throw "Wintun SHA-256 mismatch. Expected $WintunHash, received $ActualWintunHash"
}

$WintunExtract = Join-Path $Temp 'wintun-extracted'
if (Test-Path $WintunExtract) { Remove-Item $WintunExtract -Recurse -Force }
Expand-Archive -Path $WintunZip -DestinationPath $WintunExtract -Force
$WintunDll = Join-Path $WintunExtract 'wintun\bin\amd64\wintun.dll'
if (-not (Test-Path $WintunDll)) { throw "wintun.dll was not found at $WintunDll" }
Copy-Item $WintunDll (Join-Path $Bin 'wintun.dll') -Force

Write-Host ''
Write-Host 'Achan runtime components installed and SHA-256 verified:' -ForegroundColor Green
Write-Host "  tun2proxy: $($TunExe.Name) (v0.8.7)"
Write-Host '  Wintun: 0.14.1 x64'
Write-Host "  Destination: $Bin"
