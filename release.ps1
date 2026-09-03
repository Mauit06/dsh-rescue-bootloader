#Requires -Version 5.1
<#
.SYNOPSIS
  Build + push + create a GitHub Release for dsh-rescue-bootloader.
.DESCRIPTION
  1. Reads version from package.json (or -Version).
  2. Builds the .tgz via npm pack (or reuses it with -SkipPack).
  3. Force-pushes main + tags to GitHub (uses -Token for auth).
  4. Creates a GitHub Release via the REST API.
  5. Uploads the .tgz as the release asset.
.NOTES
  Requires a token with `repo` scope. Creating releases is NOT allowed by
  the `public_repo` scope (POST /releases returns 401). Pass the token via
  $env:GH_TOKEN or -Token. It is never stored to disk or echoed.
#>
[CmdletBinding()]
param(
  [Parameter()][string]$Token = $env:GH_TOKEN,
  [string]$Repo = 'Mauit06/dsh-rescue-bootloader',
  [string]$Version,
  [string]$NoteFile = 'RELEASE_BODY.md',
  [switch]$SkipPush,
  [switch]$SkipPack
)
$ErrorActionPreference = 'Stop'

if (-not $Token) { Write-Host 'ERROR: Set GH_TOKEN (or -Token) to a repo-scoped PAT.' -ForegroundColor Red; exit 1 }
if (-not $Version) {
  $pkg = Get-Content package.json -Raw -Encoding UTF8 | ConvertFrom-Json
  $Version = $pkg.version
  if (-not $Version) { Write-Host 'ERROR: no version in package.json and -Version not given.'; exit 1 }
}
$ver = "v${Version}"
$tgz = "dsh-rescue-bootloader-${Version}.tgz"

function Info($m){ Write-Host "[$((Get-Date -Format HH:mm:ss))] [release] $m" }

# 1) Build tarball if missing
if (-not (Test-Path $tgz)) {
  if ($SkipPack) { Write-Host "ERROR: $tgz missing but -SkipPack set."; exit 1 }
  Info "Running npm pack to build $tgz ..."
  npm pack | Out-Null
  if (-not (Test-Path $tgz)) { Write-Host "ERROR: npm pack did not produce $tgz"; exit 1 }
} else { Info "Reusing existing $tgz" }

# 2) Push
if (-not $SkipPush) {
  Info "Pushing main + tags ..."
  git push -f "https://${Token}@github.com/${Repo}.git" main --tags
  if ($LASTEXITCODE -ne 0) { Write-Host 'ERROR: git push failed'; exit 1 }
  Info 'Push OK'
} else { Info 'Skipping push (-SkipPush)' }

# 3) Create release
Info "Creating release $ver ..."
$headers = @{ Authorization = "Bearer $Token"; 'User-Agent' = 'dsh-agent'; Accept = 'application/vnd.github+json'; 'X-GitHub-Api-Version' = '2022-11-28' }
$note = ''
if (Test-Path $NoteFile) { $note = Get-Content $NoteFile -Raw -Encoding UTF8 }
$payload = @{ tag_name=$ver; target_commitish='main'; name="dsh-rescue-bootloader $ver"; body=$note; draft=$false; prerelease=$false } | ConvertTo-Json -Depth 5
try {
  $rel = Invoke-RestMethod -Method Post -Uri "https://api.github.com/repos/${Repo}/releases" -Headers $headers -ContentType 'application/json' -Body $payload
  Info "Release created: $($rel.html_url)"
} catch {
  Write-Host "ERROR creating release: $($_.Exception.Message)" -ForegroundColor Red
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
  exit 1
}

# 4) Upload asset
Info 'Uploading .tgz asset ...'
try {
  $up = Invoke-RestMethod -Method Post -Uri "https://uploads.github.com/repos/${Repo}/releases/$($rel.id)/assets?name=$tgz" -Headers $headers -ContentType 'application/octet-stream' -InFile $tgz
  Info "Asset uploaded: $($up.name)"
} catch {
  Write-Host "ERROR uploading asset: $($_.Exception.Message)" -ForegroundColor Red
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
  exit 1
}

Write-Host ''
Write-Host "DONE. Release URL: $($rel.html_url)" -ForegroundColor Green