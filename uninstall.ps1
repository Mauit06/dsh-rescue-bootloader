#Requires -Version 5.1
<#
.SYNOPSIS
  Uninstall dsh-rescue-bootloader plugin.
.DESCRIPTION
  1. Removes the rescue bootloader patch from dsh.cmd and dsh.ps1.
  2. Unregisters the plugin from package.json.
  3. Deletes the plugin directory (user data is removed too).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ProfileDir   = Join-Path $env:USERPROFILE '.dsh\profiles\web'
$NodeModules  = Join-Path $ProfileDir 'node_modules'
$TargetDir    = Join-Path $NodeModules 'dsh-rescue-bootloader'
$PkgJson      = Join-Path $ProfileDir 'package.json'
$NpmDir       = Join-Path $env:APPDATA 'npm'
$DshCmd       = Join-Path $NpmDir 'dsh.cmd'
$DshPs1       = Join-Path $NpmDir 'dsh.ps1'

function Write-Log($msg) {
  $ts = Get-Date -Format 'HH:mm:ss'
  Write-Host "[$ts] [uninstall] $msg"
}

$utf8 = New-Object System.Text.UTF8Encoding($false)

# 1. Unpatch dsh.cmd
Write-Log "Restoring dsh.cmd"
$cmdContent = Get-Content $DshCmd -Raw
# Remove the rescue block (from REM === DSH Rescue to the extra :rundsh)
$cmdContent = $cmdContent -replace '(?s)\r?\nREM === DSH Rescue: intercept web subcommand ===.*?:rundsh\r?\n', "`r`n:rundsh`r`n"
[System.IO.File]::WriteAllText($DshCmd, $cmdContent, $utf8)
Write-Log "dsh.cmd restored"

# 2. Unpatch dsh.ps1
Write-Log "Restoring dsh.ps1"
$psContent = Get-Content $DshPs1 -Raw
$psContent = $psContent -replace '(?s)^# === DSH Rescue: intercept web subcommand ===.*?\r?\n\r?\n', ''
[System.IO.File]::WriteAllText($DshPs1, $psContent, $utf8)
Write-Log "dsh.ps1 restored"

# 3. Unregister from package.json
Write-Log "Unregistering from package.json"
$pkg = Get-Content $PkgJson -Raw | ConvertFrom-Json
if ($pkg.dependencies.'dsh-rescue-bootloader') {
  $pkg.dependencies.PSObject.Properties.Remove('dsh-rescue-bootloader')
}
$pkg.dsh.profile.bundles = @($pkg.dsh.profile.bundles | Where-Object { $_ -ne 'dsh-rescue-bootloader' })
[System.IO.File]::WriteAllText($PkgJson, ($pkg | ConvertTo-Json -Depth 10), $utf8)
Write-Log "Unregistered from package.json"

# 4. Delete plugin directory
if (Test-Path $TargetDir) {
  Remove-Item $TargetDir -Recurse -Force
  Write-Log "Plugin directory deleted"
}

Write-Host ""
Write-Host "dsh-rescue-bootloader uninstalled."
Write-Host ""
