#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装后自动配置（替代 scripts/setup.js）。
把 dsh.cmd / dsh.ps1 改为经由 Python 启动器 dsh_rescue.py 处理 `dsh web`，
并把本次使用的 python 路径写入 data/python.path 供 lib/index.js 使用。"""
import os
import sys
import time
from pathlib import Path

PLUGIN_NAME = 'dsh-rescue-bootloader'
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
RESCUE = PLUGIN_ROOT / 'dsh_rescue.py'
PYTHON = sys.executable


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] [rescue-setup] {msg}', flush=True)


def npm_dir():
    return Path(os.environ.get('APPDATA', '')) / 'npm'


def patch_dsh_cmd(dsh_cmd, rescue):
    if not dsh_cmd.exists():
        log(f'dsh.cmd 不存在: {dsh_cmd}，跳过'); return False
    content = dsh_cmd.read_text(encoding='utf-8', errors='replace')
    if PLUGIN_NAME in content:
        log('dsh.cmd 已打过补丁'); return True
    marker = ':rundsh'
    idx = content.find(marker)
    if idx == -1:
        log('找不到 :rundsh 标签，跳过'); return False
    patch = (
        '\r\nREM === DSH Rescue: intercept web subcommand ===\r\n'
        'if /I not "%~1"=="web" goto rundsh\r\n'
        f'if not EXIST "{rescue}" goto rundsh\r\n'
        'endLocal\r\n'
        f'"{PYTHON}" "{rescue}"\r\n'
        'exit /b %ERRORLEVEL%\r\n'
        '\r\n'
    )
    content = content[:idx] + patch + content[idx:]
    dsh_cmd.write_text(content, encoding='utf-8')
    log('dsh.cmd 已打补丁')
    return True


def patch_dsh_ps1(dsh_ps1, rescue):
    if not dsh_ps1.exists():
        log(f'dsh.ps1 不存在: {dsh_ps1}，跳过'); return False
    content = dsh_ps1.read_text(encoding='utf-8', errors='replace')
    if PLUGIN_NAME in content:
        log('dsh.ps1 已打过补丁'); return True
    block = (
        '\n# === DSH Rescue: intercept web subcommand ===\n'
        'if ($args.Count -gt 0 -and $args[0] -eq \'web\') {\n'
        f'  $rescuePs = \'{rescue}\'\n'
        '  if (Test-Path $rescuePs) {\n'
        f'    & \'{PYTHON}\' $rescuePs\n'
        '    exit $LASTEXITCODE\n'
        '  }\n'
        '}\n'
    )
    lines = content.splitlines(keepends=True)
    insert_at = 0
    for i, ln in enumerate(lines):
        if ln.startswith('$basedir='):
            insert_at = i + 1
            break
    lines.insert(insert_at, block)
    dsh_ps1.write_text(''.join(lines), encoding='utf-8')
    log('dsh.ps1 已打补丁')
    return True


def main():
    if os.name != 'nt':
        log(f'非 Windows ({os.name})，跳过补丁'); return
    try:
        (PLUGIN_ROOT / 'data').mkdir(parents=True, exist_ok=True)
        (PLUGIN_ROOT / 'data' / 'python.path').write_text(PYTHON, encoding='utf-8')
    except Exception:
        pass
    if not RESCUE.exists():
        log(f'dsh_rescue.py 不存在: {RESCUE}')
        sys.exit(1)
    log(f'Python: {PYTHON}')
    log(f'Rescue launcher: {RESCUE}')
    patch_dsh_cmd(npm_dir() / 'dsh.cmd', RESCUE)
    patch_dsh_ps1(npm_dir() / 'dsh.ps1', RESCUE)
    log('安装配置完成，运行 "dsh web" 即可启用崩溃检测。')


if __name__ == '__main__':
    main()