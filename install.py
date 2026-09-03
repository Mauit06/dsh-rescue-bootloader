#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动安装脚本（备用路径；推荐用 dsh plugin --profile web add）。
复制插件到 profile 的 node_modules 并注册；崩溃检测拦截会在插件下次加载时自动安装。"""
import json
import shutil
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
PROFILE_DIR = Path.home() / '.dsh' / 'profiles' / 'web'
TARGET = PROFILE_DIR / 'node_modules' / 'dsh-rescue-bootloader'
PKG_JSON = PROFILE_DIR / 'package.json'
EXCLUDE = {'install.py', 'uninstall.py', 'data', 'tests', '__pycache__', '.git',
           'release.py', 'RELEASE_BODY.md', '_t.mjs', '.dsh-rescue-bak'}


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] [install] {msg}', flush=True)


def ignore(directory, names):
    skip = set(names) & EXCLUDE
    skip |= {n for n in names if n.endswith('-bak')}
    return skip


def main():
    if not (PLUGIN_ROOT / 'lib' / 'index.js').exists():
        log('当前目录不是插件根目录'); return 1
    log(f'复制插件到 {TARGET}')
    data_bak = None
    if TARGET.exists():
        if (TARGET / 'data').exists():
            data_bak = PLUGIN_ROOT / '_keepdata'
            shutil.copytree(TARGET / 'data', data_bak, dirs_exist_ok=True)
        shutil.rmtree(TARGET)
    shutil.copytree(PLUGIN_ROOT, TARGET, ignore=ignore)
    if data_bak:
        shutil.copytree(data_bak, TARGET / 'data', dirs_exist_ok=True)
        shutil.rmtree(data_bak, ignore_errors=True)

    log('注册到 package.json')
    pkg = json.loads(PKG_JSON.read_text(encoding='utf-8'))
    pkg.setdefault('dependencies', {})['dsh-rescue-bootloader'] = 'file:./node_modules/dsh-rescue-bootloader'
    prof = pkg.setdefault('dsh', {}).setdefault('profile', {})
    bundles = prof.setdefault('bundles', [])
    if 'dsh-rescue-bootloader' not in bundles:
        bundles.append('dsh-rescue-bootloader')
    PKG_JSON.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print()
    print('已安装。崩溃检测拦截会在 DSH 下次加载本插件时自动配置（无需任何手动步骤）。')
    print('用法: dsh web   ；管理台: http://127.0.0.1:8105')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())