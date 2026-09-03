#Requires -Version 5.1
<#
.SYNOPSIS
  DSH Rescue Bootloader — like Windows Safe Mode / Magisk rescue module.
.DESCRIPTION
  Wraps `dsh web` startup with crash monitoring. If DSH crashes during boot
  (process exits non-zero OR web port not responding within timeout), it
  automatically enters Safe Mode: disables all non-official plugins so DSH
  can boot. Then starts a recovery web console to selectively re-enable plugins.

  Official plugins = bundle names starting with "@deepseek-ai/".
.NOTES
  All changes are reversible: package.json is backed up before modification.
#>

[CmdletBinding()]
param(
  [switch]$Safe,          # Force safe mode directly
  [int]$TimeoutSec = 30,  # Boot timeout (seconds)
  [int]$DshPort = 3080,   # DSH web port
  [int]$RescuePort = 8105 # Rescue console port
)

$ErrorActionPreference = 'Stop'

# ============ Paths ============
# $PSScriptRoot = 插件目录 (dsh-rescue-bootloader/)
$PluginDir    = $PSScriptRoot
$ProfileDir   = "$env:USERPROFILE\.dsh\profiles\web"
$PkgJson      = Join-Path $ProfileDir 'package.json'
$BackupPath   = Join-Path $ProfileDir 'package.json.rescue-backup'
# 数据目录：插件内 data/
$RescueDir    = Join-Path $PluginDir 'data'
$CrashFlag    = Join-Path $RescueDir '.crash-flag'
$ServerScript = Join-Path $PluginDir 'rescue-server.mjs'
$StateFile    = Join-Path $RescueDir 'state.json'
$WhitelistFile= Join-Path $RescueDir 'whitelist.json'
$CrashLogDir  = Join-Path $RescueDir 'crash-logs'
$BootLogFile  = Join-Path $RescueDir 'last-boot.log'

# ============ Helpers ============
function Write-Log($msg) {
  $ts = Get-Date -Format 'HH:mm:ss'
  Write-Host "[$ts] [rescue] $msg"
}

function Test-Port($port) {
  try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect('127.0.0.1', $port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(800, $false)
    $tcp.Close()
    return $ok
  } catch { return $false }
}

function Get-OfficialBundles($bundles) {
  return @($bundles | Where-Object { $_ -match '^@deepseek-ai/' })
}

function Backup-PackageJson {
  if (Test-Path $PkgJson) {
    Copy-Item $PkgJson $BackupPath -Force
    Write-Log "Backed up package.json -> package.json.rescue-backup"
  }
}

function Get-Whitelist {
  if (Test-Path $WhitelistFile) {
    try {
      $wl = Get-Content $WhitelistFile -Raw | ConvertFrom-Json
      return @($wl)
    } catch { return @() }
  }
  return @()
}

function Enter-SafeMode {
  Write-Log "========== ENTERING SAFE MODE =========="
  Backup-PackageJson
  $json = Get-Content $PkgJson -Raw | ConvertFrom-Json
  $allBundles = @($json.dsh.profile.bundles)
  $official = Get-OfficialBundles $allBundles
  $whitelist = Get-Whitelist
  # Keep official + whitelisted; disable the rest
  $keep = @($official + $whitelist | Select-Object -Unique)
  $disabled = @($allBundles | Where-Object { $keep -notcontains $_ })

  $json.dsh.profile.bundles = $keep
  $jsonText = $json | ConvertTo-Json -Depth 10
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($PkgJson, $jsonText, $utf8NoBom)

  Write-Log "Kept official ($($official.Count)): $($official -join ', ')"
  if ($whitelist.Count -gt 0) {
    Write-Log "Kept whitelisted ($($whitelist.Count)): $($whitelist -join ', ')"
  }
  Write-Log "Disabled ($($disabled.Count)): $($disabled -join ', ')"

  $state = @{
    safeMode   = $true
    allBundles = @($allBundles)
    official   = @($official)
    whitelist  = @($whitelist)
    disabled   = @($disabled)
    port       = $RescuePort
  }
  $stateText = $state | ConvertTo-Json -Depth 5
  [System.IO.File]::WriteAllText($StateFile, $stateText, $utf8NoBom)
  [System.IO.File]::WriteAllText($CrashFlag, '1', $utf8NoBom)
}

function Exit-SafeMode {
  if (Test-Path $BackupPath) {
    Copy-Item $BackupPath $PkgJson -Force
    Write-Log "Restored original package.json"
  }
  Remove-Item $CrashFlag -ErrorAction SilentlyContinue
  Remove-Item $StateFile -ErrorAction SilentlyContinue
}

function Start-DshWeb {
  Write-Log "Starting dsh web (port $DshPort)..."
  # 直接用 node 运行 bin.js，不经过 dsh.cmd（避免 dsh.cmd 转发到 rescue 造成递归）
  $binJs = Join-Path $env:APPDATA 'npm\node_modules\@deepseek-ai\dsh\lib\bin.js'
  if (-not (Test-Path $binJs)) {
    # 回退：通过 dsh.cmd 查找
    $dshCmd = Join-Path $env:APPDATA 'npm\dsh.cmd'
    if (Test-Path $dshCmd) {
      $binJs = Join-Path $env:APPDATA 'npm\node_modules\@deepseek-ai\dsh\lib\bin.js'
    }
  }
  $nodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
  if (-not $nodeExe) { $nodeExe = 'node' }
  try {
    $proc = Start-Process -FilePath $nodeExe `
      -ArgumentList "`"$binJs`"", 'web' `
      -WorkingDirectory $ProfileDir `
      -RedirectStandardOutput $BootLogFile `
      -RedirectStandardError  "$BootLogFile.err" `
      -PassThru -WindowStyle Hidden
  } catch {
    throw
  }
  return $proc
}

function Save-CrashLog($reason) {
  if (-not (Test-Path $CrashLogDir)) {
    New-Item -ItemType Directory -Path $CrashLogDir -Force | Out-Null
  }
  $ts = Get-Date -Format 'yyyyMMdd-HHmmss'
  $logFile = Join-Path $CrashLogDir "crash-$ts.log"
  $sb = New-Object System.Text.StringBuilder
  [void]$sb.AppendLine("=== DSH Crash Log ===")
  [void]$sb.AppendLine("Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
  [void]$sb.AppendLine("Reason: $reason")
  [void]$sb.AppendLine("")
  if (Test-Path $BootLogFile) {
    [void]$sb.AppendLine("--- stdout ---")
    [void]$sb.AppendLine((Get-Content $BootLogFile -Raw -ErrorAction SilentlyContinue))
  }
  $errFile = "$BootLogFile.err"
  if (Test-Path $errFile) {
    [void]$sb.AppendLine("--- stderr ---")
    [void]$sb.AppendLine((Get-Content $errFile -Raw -ErrorAction SilentlyContinue))
  }
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($logFile, $sb.ToString(), $utf8NoBom)
  Write-Log "Crash log saved: $logFile"
  # Also keep a "latest" copy for the UI
  Copy-Item $logFile (Join-Path $CrashLogDir 'latest.log') -Force
}

function Start-RescueServer {
  Write-Log "Starting rescue console http://127.0.0.1:$RescuePort"
  Start-Process -FilePath 'node' `
    -ArgumentList $ServerScript, $RescuePort, $ProfileDir, $RescueDir `
    -WindowStyle Hidden -PassThru | Out-Null
}

function Wait-ForStartup($proc, $timeoutSec) {
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) {
      return @{ ok = $false; reason = "process exited (code=$($proc.ExitCode))" }
    }
    if (Test-Port $DshPort) {
      return @{ ok = $true; reason = "port $DshPort responding" }
    }
    Start-Sleep -Milliseconds 500
  }
  return @{ ok = $false; reason = "timeout ($timeoutSec sec)" }
}

# ============ Main ============
Write-Log "DSH Rescue Bootloader v1.0"
Write-Log "Profile: $ProfileDir"

if (-not (Test-Path $RescueDir)) {
  New-Item -ItemType Directory -Path $RescueDir -Force | Out-Null
}

$forceSafe = $Safe.IsPresent -or (Test-Path $CrashFlag)
if ($forceSafe) {
  if (Test-Path $CrashFlag) {
    Write-Log "Crash flag detected, entering safe mode"
  } else {
    Write-Log "--Safe specified, entering safe mode"
  }
  Enter-SafeMode
  Get-Process -Name node -ErrorAction SilentlyContinue |
    Where-Object { $_.StartTime -gt (Get-Date).AddHours(-1) } |
    Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2

  $dsh = Start-DshWeb
  Start-RescueServer
  Write-Log ""
  Write-Log "========== SAFE MODE STARTED =========="
  Write-Log "DSH Web:       http://127.0.0.1:$DshPort"
  Write-Log "Rescue console: http://127.0.0.1:$RescuePort"
  Write-Log "Selectively re-enable plugins in the console, then Apply & Restart"
  Write-Log "======================================"
  $dsh.WaitForExit()
  return
}

Write-Log "Normal boot, monitoring (timeout $TimeoutSec sec)..."
$dsh = Start-DshWeb
$result = Wait-ForStartup $dsh $TimeoutSec

if ($result.ok) {
  Write-Log "DSH port responding, running stability check (5 sec)..."
  # DSH may open the port before finishing bundle loading; crash can happen right after.
  $stabDeadline = (Get-Date).AddSeconds(5)
  $crashedAfterStart = $false
  while ((Get-Date) -lt $stabDeadline) {
    if ($dsh.HasExited) { $crashedAfterStart = $true; break }
    Start-Sleep -Milliseconds 500
  }
  if ($crashedAfterStart) {
    Write-Log "DSH crashed shortly after startup (exit code $($dsh.ExitCode))"
    Save-CrashLog "process exited shortly after port responded (code=$($dsh.ExitCode))"
    Write-Log "Triggering rescue..."
    Start-Sleep -Seconds 2
    Enter-SafeMode
    $dsh = Start-DshWeb
    Start-RescueServer
    $result2 = Wait-ForStartup $dsh 20
    if ($result2.ok) {
      Write-Log ""
      Write-Log "========== SAFE MODE OK =========="
      Write-Log "DSH Web (official+whitelist): http://127.0.0.1:$DshPort"
      Write-Log "Rescue console:               http://127.0.0.1:$RescuePort"
      Write-Log "Re-enable plugins one by one to find the culprit"
      Write-Log "=================================="
    } else {
      Write-Log "Safe mode also failed: $($result2.reason)"
      Write-Log "Core may be broken; check dsh installation."
    }
    $dsh.WaitForExit()
    return
  }
  Write-Log "DSH started OK and stable: $($result.reason)"
  Write-Log "DSH Web: http://127.0.0.1:$DshPort"
  Write-Log "Rescue console: http://127.0.0.1:$RescuePort"
  Write-Log "(running in background; closing this window stops DSH)"
  $dsh.WaitForExit()
} else {
  Write-Log "DSH boot FAILED: $($result.reason)"
  Save-CrashLog $result.reason
  Write-Log "Triggering rescue..."
  if (-not $dsh.HasExited) { $dsh.Kill() }
  Start-Sleep -Seconds 2

  Enter-SafeMode

  $dsh = Start-DshWeb
  Start-RescueServer

  $result2 = Wait-ForStartup $dsh 20
  if ($result2.ok) {
    Write-Log ""
    Write-Log "========== SAFE MODE OK =========="
    Write-Log "DSH Web (official only): http://127.0.0.1:$DshPort"
    Write-Log "Rescue console:          http://127.0.0.1:$RescuePort"
    Write-Log "Re-enable plugins one by one to find the culprit"
    Write-Log "=================================="
  } else {
    Write-Log "Safe mode also failed: $($result2.reason)"
    Write-Log "Core may be broken; check dsh installation."
  }
  $dsh.WaitForExit()
}