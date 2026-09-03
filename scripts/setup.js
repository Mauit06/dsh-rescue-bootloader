/**
 * dsh-rescue-bootloader setup script
 *
 * Runs automatically after `dsh plugin add` (postinstall) or manually via install.ps1.
 * Patches dsh.cmd and dsh.ps1 so that `dsh web` is routed through the rescue
 * bootloader for crash detection and safe mode.
 *
 * Only runs on Windows (dsh.cmd/dsh.ps1 are Windows-specific).
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const PLUGIN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PLUGIN_NAME = 'dsh-rescue-bootloader';

function log(msg) {
  const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  console.log(`[${ts}] [rescue-setup] ${msg}`);
}

function patchDshCmd(dshCmdPath, rescuePsPath) {
  if (!fs.existsSync(dshCmdPath)) {
    log(`dsh.cmd not found at ${dshCmdPath}, skipping`);
    return false;
  }
  let content = fs.readFileSync(dshCmdPath, 'utf8');
  if (content.includes(PLUGIN_NAME)) {
    log('dsh.cmd already patched');
    return true;
  }

  // Escape backslashes for batch file
  const escapedPs = rescuePsPath.replace(/\\/g, '\\');
  const marker = ':rundsh';
  const idx = content.indexOf(marker);
  if (idx === -1) {
    log('Could not find :rundsh label in dsh.cmd, skipping');
    return false;
  }

  const patch =
    `\r\nREM === DSH Rescue: intercept web subcommand ===\r\n` +
    `if /I not "%~1"=="web" goto rundsh\r\n` +
    `if not EXIST "${escapedPs}" goto rundsh\r\n` +
    `endLocal\r\n` +
    `powershell -NoProfile -ExecutionPolicy Bypass -File "${escapedPs}"\r\n` +
    `exit /b %ERRORLEVEL%\r\n` +
    `\r\n`;

  content = content.slice(0, idx) + patch + content.slice(idx);
  fs.writeFileSync(dshCmdPath, content, 'utf8');
  log('dsh.cmd patched');
  return true;
}

function patchDshPs1(dshPs1Path, rescuePsPath) {
  if (!fs.existsSync(dshPs1Path)) {
    log(`dsh.ps1 not found at ${dshPs1Path}, skipping`);
    return false;
  }
  let content = fs.readFileSync(dshPs1Path, 'utf8');
  if (content.includes(PLUGIN_NAME)) {
    log('dsh.ps1 already patched');
    return true;
  }

  const patch =
    `# === DSH Rescue: intercept web subcommand ===\r\n` +
    `if ($args.Count -gt 0 -and $args[0] -eq 'web') {\r\n` +
    `  $rescuePs = '${rescuePsPath}'\r\n` +
    `  if (Test-Path $rescuePs) {\r\n` +
    `    & $rescuePs\r\n` +
    `    exit $LASTEXITCODE\r\n` +
    `  }\r\n` +
    `}\r\n` +
    `\r\n`;

  content = patch + content;
  // PS 5.1 reads a BOM-less .ps1 as ANSI (GBK on zh-CN Windows), garbling non-ASCII.
  // Write UTF-8 WITH BOM so any localized comment stays intact; ASCII content unaffected.
  fs.writeFileSync(dshPs1Path, '\ufeff' + content, 'utf8');
  log('dsh.ps1 patched');
  return true;
}

function main() {
  // Only Windows uses dsh.cmd / dsh.ps1
  if (process.platform !== 'win32') {
    log(`Non-Windows platform (${process.platform}), skipping dsh.cmd/dsh.ps1 patch`);
    return;
  }

  const npmDir = path.join(os.homedir(), 'AppData', 'Roaming', 'npm');
  const dshCmd = path.join(npmDir, 'dsh.cmd');
  const dshPs1 = path.join(npmDir, 'dsh.ps1');
  const rescuePs = path.join(PLUGIN_ROOT, 'dsh-rescue.ps1');

  if (!fs.existsSync(rescuePs)) {
    log(`dsh-rescue.ps1 not found at ${rescuePs}`);
    process.exit(1);
  }

  log(`Rescue script: ${rescuePs}`);
  patchDshCmd(dshCmd, rescuePs);
  patchDshPs1(dshPs1, rescuePs);

  log('Setup complete. Run "dsh web" to start with crash detection.');
}

main();
