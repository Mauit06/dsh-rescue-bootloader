#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两级安全模式状态仿真回归：临时 profile 全流程，不触碰真实机器。"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dsh_rescue as D
import rescue_server as S

fails = 0


def ok(cond, msg):
    global fails
    print(('PASS: ' if cond else 'FAIL: ') + msg)
    if not cond:
        fails += 1


def main():
    tmp = Path(tempfile.mkdtemp())
    ORIG = ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', 'dshmarket', 'dsh-notifier', 'dsh-history', 'git-graph', 'dsh-rescue-bootloader']
    pkg = {'name': 'p',
           'dependencies': {'@deepseek-ai/dsh-web-app': '0.1.2-rc.1', 'dshmarket': '^1.0', 'dsh-notifier': '^0.9',
                            'dsh-history': '^0.1', 'git-graph': '^0.3', 'dsh-rescue-bootloader': '^1.0'},
           'dsh': {'profile': {'bundles': list(ORIG)}}}
    (tmp / 'package.json').write_text(json.dumps(pkg), encoding='utf-8')
    (tmp / 'whitelist.json').write_text(json.dumps(['dsh-notifier']), encoding='utf-8')
    for M in (D, S):
        M.PROFILE_DIR = tmp
    for attr in ('PKG_JSON', 'BACKUP', 'STATE_FILE', 'CRASH_FLAG', 'WHITELIST_FILE'):
        setattr(D, attr, tmp / {'PKG_JSON': 'package.json', 'BACKUP': 'package.json.rescue-backup',
                                'STATE_FILE': 'state.json', 'CRASH_FLAG': '.crash-flag',
                                'WHITELIST_FILE': 'whitelist.json'}[attr])
        setattr(S, attr, tmp / {'PKG_JSON': 'package.json', 'BACKUP': 'package.json.rescue-backup',
                                'STATE_FILE': 'state.json', 'CRASH_FLAG': '.crash-flag',
                                'WHITELIST_FILE': 'whitelist.json'}[attr])
    S.CRASH_LOG_DIR = tmp / 'crash-logs'
    S.PID_FILE = tmp / 'dsh.pid'

    D.enter_safe_mode(1, True)
    cur1 = json.loads(D.PKG_JSON.read_text(encoding='utf-8'))['dsh']['profile']['bundles']
    ok('dsh-notifier' in cur1 and 'dshmarket' not in cur1, 'crash1: 官方+白名单保留')
    D.enter_safe_mode(2, True)
    cur2 = json.loads(D.PKG_JSON.read_text(encoding='utf-8'))['dsh']['profile']['bundles']
    ok(all(b.startswith('@deepseek-ai/') or b == 'dsh-rescue-bootloader' for b in cur2), 'crash2: 官方+救援自保(白名单也禁)')
    st = S.get_current_state()
    missing = [b for b in ORIG if b not in st['disabled'] and b not in cur2 and b != 'dsh-rescue-bootloader']
    ok(not missing, 'crash2 后管理台列表完整: ' + str(st['disabled']))
    bk = json.loads(D.BACKUP.read_text(encoding='utf-8'))['dsh']['profile']['bundles']
    ok(set(bk) >= set(ORIG), '备份携带全集清单')

    # 损坏数据兜底：state/备份都被写成官方专属时，依赖表恢复列表
    broken = {'name': 'p', 'dependencies': {'dshmarket': '^1', 'dsh-notifier': '^0.9'},
              'dsh': {'profile': {'bundles': ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app']}}}
    D.PKG_JSON.write_text(json.dumps(broken), encoding='utf-8')
    D.STATE_FILE.write_text(json.dumps({'safeMode': True, 'crashCount': 2, 'allBundles': ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app']}), encoding='utf-8')
    D.BACKUP.write_text(json.dumps(broken), encoding='utf-8')
    st2 = S.get_current_state()
    ok('dshmarket' in st2['disabled'] and 'dsh-notifier' in st2['disabled'], '损坏数据下依赖表兜底')
    return 0 if fails == 0 else 1


if __name__ == '__main__':
    sys.exit(main())