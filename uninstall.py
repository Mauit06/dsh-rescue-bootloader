#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卸载脚本（替代 uninstall.ps1）。
1. 还原 dsh.cmd/dsh.ps1；2. 从 package.json 注销；3. 删除插件目录。"""
import json
import re
import shutil
import time
from pathlib import Path

PROFILE_DIR = Path.home() / '.dsh' / 'profiles' / 'web'
NODE_MODULES = PROFILE_DIR / 'node_modules'
TARGET = NODE_MODULES / 'dsh-rescue-bootloader'
PKG_JSON = PROFILE_DIR / 'package.json'
NPM_DIR = Path(__import__('os').environ.get('APPDATA', '')) / 'npm'
DSH_CMD = NPM_DIR / 'dsh.cmd'
DSH_PS1 = NPM_DIR / 'dsh.ps1'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] [uninstall] {msg}', flush=True)


def main():
    log('还原 dsh.cmd')
    if DSH_CMD.exists():
        c = DSH_CMD.read_text(encoding='utf-8', errors='replace')
        c = re.sub(r'\r?\nREM === DSH Rescue:.*?:rundsh', '\r\n:rundsh', c, flags=re.S)
        DSH_CMD.write_text(c, encoding='utf-8')
        log('dsh.cmd 已还原')

    log('还原 dsh.ps1')
    if DSH_PS1.exists():
        p = DSH_PS1.read_text(encoding='utf-8', errors='replace')
        p = re.sub(r'(?m)^# === DSH Rescue:.*?\r?\n\r?\n', '', p)
        DSH_PS1.write_text(p, encoding='utf-8')
        log('dsh.ps1 已还原')

    log('从 package.json 注销')
    if PKG_JSON.exists():
        pkg = json.loads(PKG_JSON.read_text(encoding='utf-8'))
        pkg.get('dependencies', {}).pop('dsh-rescue-bootloader', None)
        prof = pkg.get('dsh', {}).get('profile', {})
        if 'bundles' in prof:
            prof['bundles'] = [b for b in prof['bundles'] if b != 'dsh-rescue-bootloader']
        PKG_JSON.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        log('已注销')

    if TARGET.exists():
        shutil.rmtree(TARGET)
        log('插件目录已删除')

    print()
    print('dsh-rescue-bootloader 已卸载。')


if __name__ == '__main__':
    main()