#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动安装脚本（替代 install.ps1）。
1. 复制插件到 profile 的 node_modules；2. 注册到 package.json；3. 运行 scripts/setup.py 打补丁。"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent
PROFILE_DIR = Path.home() / '.dsh' / 'profiles' / 'web'
NODE_MODULES = PROFILE_DIR / 'node_modules'
TARGET = NODE_MODULES / 'dsh-rescue-bootloader'
PKG_JSON = PROFILE_DIR / 'package.json'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] [install] {msg}', flush=True)


def ignore(directory, names):
    return {'install.py', 'uninstall.py', 'data'} & set(names)


def main():
    log(f'复制插件到 {TARGET}')
    if TARGET.exists():
        tmp = TARGET / 'data'
        if tmp.exists():
            shutil.copytree(tmp, PKG_JSON.parent / '_dsh_rescue_data_bak', dirs_exist_ok=True)
        shutil.rmtree(TARGET)
        TARGET.mkdir(parents=True, exist_ok=True)
    else:
        TARGET.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PLUGIN_ROOT, TARGET, dirs_exist_ok=True, ignore=ignore)
    bak = PKG_JSON.parent / '_dsh_rescue_data_bak'
    if bak.exists():
        shutil.copytree(bak, TARGET / 'data', dirs_exist_ok=True)
        shutil.rmtree(bak)

    log('注册到 package.json')
    pkg = json.loads(PKG_JSON.read_text(encoding='utf-8'))
    pkg.setdefault('dependencies', {})
    pkg['dependencies']['dsh-rescue-bootloader'] = 'file:./node_modules/dsh-rescue-bootloader'
    prof = pkg.setdefault('dsh', {}).setdefault('profile', {})
    bundles = prof.setdefault('bundles', [])
    if 'dsh-rescue-bootloader' not in bundles:
        bundles.append('dsh-rescue-bootloader')
    PKG_JSON.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    log('运行 scripts/setup.py 打补丁')
    r = subprocess.run([sys.executable, str(TARGET / 'scripts' / 'setup.py')])
    if r.returncode != 0:
        log('setup.py 失败，退出码 ' + str(r.returncode))
        sys.exit(1)

    print()
    print('==========================================')
    print('  dsh-rescue-bootloader 已安装!')
    print('==========================================')
    print()
    print('用法: dsh web        # 启动 DSH 并开启崩溃检测 + 安全模式')
    print('救砖管理台: http://127.0.0.1:8105')
    print('DSH web:     http://127.0.0.1:3080')


if __name__ == '__main__':
    main()