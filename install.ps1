#Requires -Version 5.1
<#
.SYNOPSIS
  Manual installer for dsh-rescue-bootloader.
.DESCRIPTION
  1. Copies the plugin into the DSH web profile's node_modules.
  2. Registers the plugin in the profile's package.json (dependencies + bundles).
  3. Runs scripts/setup.js to patch dsh.cmd and dsh.ps1 for web interception.
.NOTES
  For the official install method, use: dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$PluginRoot   = $PSScriptRoot
$ProfileDir   = Join-Path $env:USERPROFILE '.dsh\profiles\web'
$NodeModules  = Join-Path $ProfileDir 'node_modules'
$TargetDir    = Join-Path $NodeModules 'dsh-rescue-bootloader'
$PkgJson      = Join-Path $ProfileDir 'package.json'

function Write-Log($msg) {
  $ts = Get-Date -Format 'HH:mm:ss'
  Write-Host "[$ts] [install] $msg"
}

# 1. Copy plugin files
Write-Log "Copying plugin to $TargetDir"
if (Test-Path $TargetDir) {
  # Preserve user data (data/ directory) if reinstalling
  $dataBackup = Join-Path $env:TEMP 'dsh-rescue-data-backup'
  if (Test-Path (Join-Path $TargetDir 'data')) {
    Copy-Item (Join-Path $TargetDir 'data') $dataBackup -Recurse -Force
  }
  Remove-Item $TargetDir -Recurse -Force
  New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
  if (Test-Path $dataBackup) {
    Copy-Item $dataBackup (Join-Path $TargetDir 'data') -Recurse -Force
    Remove-Item $dataBackup -Recurse -Force
  }
} else {
  New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

# Copy all files except install scripts and data
Get-ChildItem $PluginRoot -Force | Where-Object {
  $_.Name -notin @('install.ps1', 'uninstall.ps1', 'data') -and $_.Name -notlike '*.zip'
} | ForEach-Object {
  Copy-Item $_.FullName (Join-Path $TargetDir $_.Name) -Recurse -Force
}
Write-Log "Plugin files copied"

# 2. Register in package.json
Write-Log "Registering plugin in package.json"
$pkg = Get-Content $PkgJson -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $pkg.dependencies) { $pkg | Add-Member -NotePropertyName dependencies -NotePropertyValue ([pscustomobject]@{}) }
$pkg.dependencies | Add-Member -NotePropertyName 'dsh-rescue-bootloader' -NotePropertyValue 'file:./node_modules/dsh-rescue-bootloader' -Force
if (-not ($pkg.dsh.profile.bundles -contains 'dsh-rescue-bootloader')) {
  $pkg.dsh.profile.bundles = @($pkg.dsh.profile.bundles + 'dsh-rescue-bootloader')
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($PkgJson, ($pkg | ConvertTo-Json -Depth 10), $utf8)
Write-Log "Registered in package.json"

# 3. Run setup.js to patch dsh.cmd / dsh.ps1
Write-Log "Running setup.js to patch dsh.cmd / dsh.ps1"
$setupJs = Join-Path $TargetDir 'scripts\setup.js'
& node $setupJs
if ($LASTEXITCODE -ne 0) {
  Write-Log "setup.js failed with exit code $LASTEXITCODE"
  exit 1
}

Write-Host ""
Write-Host "=========================================="
Write-Host "  dsh-rescue-bootloader installed!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Usage:"
Write-Host "  dsh web          # Start DSH with crash detection + safe mode"
Write-Host ""
Write-Host "Rescue console: http://127.0.0.1:8105"
Write-Host "DSH web:         http://127.0.0.1:3080"
Write-Host ""
