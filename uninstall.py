#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卸载/还原脚本（可独立运行，也用于自动卸载失败时的兜底）。
还原 dsh.cmd / dsh.ps1 / dsh 包装脚本，注销 package.json，删除插件目录与独立副本。"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

MARKER = '=== DSH Rescue: intercept web subcommand ==='
END = '=== DSH Rescue: end ==='
PROFILE_DIR = Path.home() / '.dsh' / 'profiles' / 'web'
PKG_JSON = PROFILE_DIR / 'package.json'
TARGET = PROFILE_DIR / 'node_modules' / 'dsh-rescue-bootloader'
STANDALONE = Path.home() / '.dsh' / 'dsh-rescue-uninstall.py'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] [uninstall] {msg}', flush=True)


def shim_files():
    dirs = []
    if os.environ.get('APPDATA'):
        dirs.append(Path(os.environ['APPDATA']) / 'npm')
    if os.name == 'nt':
        dirs.append(Path.home() / 'AppData' / 'Roaming' / 'npm')
    else:
        dirs += [Path(sys.prefix) / 'bin', Path.home() / '.npm-global' / 'bin', Path('/usr/local/bin')]
    out = []
    seen = set()
    for d in dirs:
        for f in ('dsh.cmd', 'dsh.ps1', 'dsh'):
            p = d / f
            key = str(p).lower() if os.name == 'nt' else str(p)
            if p.is_file() and key not in seen:
                seen.add(key)
                out.append(p)
    return out


def strip_batch(c):
    changed = False
    while True:
        i = c.find('REM ' + MARKER)
        if i < 0:
            break
        x = c.find('exit /b %ERRORLEVEL%', i)
        if x < 0:
            return c, changed
        e = c.find('\n', x)
        c = c[:i] + c[(len(c) if e < 0 else e + 1):]
        changed = True
    fi = c.find(':rundsh')
    if fi >= 0 and fi + 7 < len(c) and c[fi + 7] not in ('\r', '\n'):
        c = c[:fi + 7] + '\r\n' + c[fi + 7:]
        changed = True
    if ':rundsh' not in c:
        anchor = c.find('endLocal & goto #_undefined_#')
        if anchor < 0:
            return c, changed
        head = c[:anchor]
        c = head + ':rundsh' + ('' if head.endswith('\n') else '\r\n') + c[anchor:]
        changed = True
    return c, changed


def strip_marker(c):
    changed = False
    while True:
        i = c.find('# === DSH Rescue:')
        if i < 0:
            return c, changed
        if c.startswith('# ' + END, i):
            n = c.find('\n', i)
            end = len(c) if n < 0 else n + 1
        else:
            e = c.find('# ' + END, i)
            if e >= 0:
                n = c.find('\n', e)
                end = len(c) if n < 0 else n + 1
            else:
                a = c.find('\n\n', i)
                b = c.find('\r\n\r\n', i)
                cands = [x for x in (a, b) if x >= 0]
                if not cands:
                    return c, changed
                n = min(cands)
                end = n + 4 if c[n] == '\r' else n + 2
        c = c[:i] + c[end:]
        changed = True


def main():
    for p in shim_files():
        try:
            raw = p.read_text(encoding='utf-8', errors='replace')
            if MARKER not in raw:
                continue
            if p.name == 'dsh.cmd':
                new, did = strip_batch(raw)
                if ':rundsh' not in new:
                    log(f'跳过 {p}：结构校验失败'); continue
            else:
                new, did = strip_marker(raw)
            if did and new != raw:
                p.write_text(new, encoding='utf-8')
                log(f'已还原 {p}')
        except Exception as ex:
            log(f'处理 {p} 失败: {ex}')

    if PKG_JSON.exists():
        try:
            pkg = json.loads(PKG_JSON.read_text(encoding='utf-8'))
            changed = False
            if pkg.get('dependencies', {}).pop('dsh-rescue-bootloader', None) is not None:
                changed = True
            prof = pkg.get('dsh', {}).get('profile', {})
            if 'dsh-rescue-bootloader' in prof.get('bundles', []):
                prof['bundles'] = [b for b in prof['bundles'] if b != 'dsh-rescue-bootloader']
                changed = True
            if changed:
                PKG_JSON.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                log('已从 package.json 注销')
        except Exception as ex:
            log(f'修改 package.json 失败: {ex}')

    here = Path(__file__).resolve().parent
    if TARGET.exists() and here == TARGET.resolve():
        log('插件目录由 dsh plugin remove 管理，保留本次运行所需文件；如需彻底删除请先还原包装脚本后手动移除')
    try:
        if STANDALONE.exists() and Path(__file__).resolve() != STANDALONE:
            STANDALONE.unlink()
    except Exception:
        pass
    log('完成。备份文件 *.dsh-rescue-bak 保留在原目录，确认无误后可自行删除。')


if __name__ == '__main__':
    main()