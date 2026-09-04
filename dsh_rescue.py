#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DSH 救砖模块 - Python 启动器（替代 dsh-rescue.ps1）

职责：
  - 启动 DSH (node .../dsh/lib/bin.js web) 并监控启动
  - 崩溃检测 -> 两级安全模式（第1次保留白名单，第2次连白名单也禁用）
  - 记录 DSH 主体版本到 state.json
  - 崩溃时启动/重启救砖管理台 (rescue_server.py)
纯标准库，无三方依赖。
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# Windows：子进程一律无控制台窗口（防闪窗）
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

# ---------- 路径 ----------
PLUGIN_DIR = Path(__file__).resolve().parent
DATA_DIR = PLUGIN_DIR / 'data'
PROFILE_DIR = Path.home() / '.dsh' / 'profiles' / 'web'
PKG_JSON = PROFILE_DIR / 'package.json'
BACKUP = PROFILE_DIR / 'package.json.rescue-backup'
STATE_FILE = DATA_DIR / 'state.json'
CRASH_FLAG = DATA_DIR / '.crash-flag'
WHITELIST_FILE = DATA_DIR / 'whitelist.json'
CRASH_LOG_DIR = DATA_DIR / 'crash-logs'
BOOT_LOG = DATA_DIR / 'last-boot.log'
BOOT_LOG_ERR = DATA_DIR / 'last-boot.log.err'
PID_FILE = DATA_DIR / 'dsh.pid'
RESCUE_SERVER = PLUGIN_DIR / 'rescue_server.py'

DEFAULT_DSH_PORT = 3080
DEFAULT_RESCUE_PORT = 8105
OFFICIAL_PREFIX = '@deepseek-ai/'


def log(msg: str) -> None:
    print(f'[{time.strftime("%H:%M:%S")}] [rescue] {msg}', flush=True)


def is_official(name: str) -> bool:
    return name.startswith(OFFICIAL_PREFIX)


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def get_dsh_version() -> str:
    pkg = read_json(PKG_JSON)
    if pkg:
        deps = pkg.get('dependencies', {}) or {}
        for k in ('@deepseek-ai/dsh-web-app', '@deepseek-ai/dsh', '@deepseek-ai/dsh-base'):
            if deps.get(k):
                return str(deps[k])
    return 'unknown'


def get_state() -> dict:
    st = read_json(STATE_FILE)
    if st is None:
        return {'safeMode': False, 'crashCount': 0, 'dshVersion': 'unknown'}
    return {
        'safeMode': bool(st.get('safeMode')),
        'crashCount': int(st.get('crashCount') or 0),
        'dshVersion': str(st.get('dshVersion') or 'unknown'),
    }


def write_state(state: dict) -> None:
    write_json(STATE_FILE, state)


def reset_crash_state() -> None:
    CRASH_FLAG.unlink(missing_ok=True)
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    log('崩溃状态已复位（清除安全模式）')


def get_whitelist() -> list:
    wl = read_json(WHITELIST_FILE)
    if isinstance(wl, list):
        return wl
    if isinstance(wl, str):
        return [wl]
    return []


def get_bin_js():
    cands = []
    if os.environ.get('APPDATA'):
        cands.append(Path(os.environ['APPDATA']) / 'npm' / 'node_modules' / '@deepseek-ai' / 'dsh' / 'lib' / 'bin.js')
    if os.environ.get('USERPROFILE'):
        cands.append(Path(os.environ['USERPROFILE']) / 'AppData' / 'Roaming' / 'npm' / 'node_modules' / '@deepseek-ai' / 'dsh' / 'lib' / 'bin.js')
    cands.append(PROFILE_DIR / 'node_modules' / '@deepseek-ai' / 'dsh' / 'lib' / 'bin.js')
    cands.append(PROFILE_DIR / 'node_modules' / '@deepseek-ai' / 'dsh-web-app' / 'lib' / 'bin.js')
    for c in cands:
        if c and c.exists():
            return c
    return cands[0] if cands else None


def is_port_open(port: int, host='127.0.0.1', timeout=1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_node() -> str:
    node = shutil.which('node')
    if not node:
        raise RuntimeError('找不到 node，请确认已安装 Node.js')
    return node


def launch_dsh() -> subprocess.Popen:
    bin_js = get_bin_js()
    if not bin_js:
        raise RuntimeError('找不到 DSH bin.js，请确认 dsh 已全局安装')
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log(f'启动 DSH: {bin_js} web')
    stdout = open(BOOT_LOG, 'wb')
    stderr = open(BOOT_LOG_ERR, 'wb')
    # Windows：给 DSH 一个「自己的隐藏控制台」(CREATE_NEW_CONSOLE + SW_HIDE)。
    # 之前用 DETACHED_PROCESS 使 DSH 无控制台 → 它每次 spawn 控制台子进程
    # (pwsh/python 工具调用) 都要新建可见窗口 = WebUI 每操作闪 PowerShell 黑窗。
    # 隐藏新控制台后：子进程继承隐藏控制台(不闪窗)，且关终端窗口不杀 DSH。
    if os.name == 'nt':
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        proc = subprocess.Popen(
            [get_node(), str(bin_js), 'web'],
            cwd=str(PROFILE_DIR), stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            startupinfo=si,
        )
    else:
        proc = subprocess.Popen(
            [get_node(), str(bin_js), 'web'],
            cwd=str(PROFILE_DIR), stdout=stdout, stderr=stderr,
        )
    PID_FILE.write_text(str(proc.pid), encoding='utf-8')
    return proc


def start_rescue_server() -> subprocess.Popen:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log(f'启动救砖管理台 http://127.0.0.1:{DEFAULT_RESCUE_PORT}')
    return subprocess.Popen(
        [sys.executable, str(RESCUE_SERVER), str(DEFAULT_RESCUE_PORT), str(PROFILE_DIR), str(DATA_DIR)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=str(PLUGIN_DIR), creationflags=NO_WINDOW,
    )


def wait_for_startup(proc, timeout) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return {'ok': False, 'reason': f'进程退出 (code={proc.returncode})'}
        if is_port_open(DEFAULT_DSH_PORT):
            return {'ok': True, 'reason': f'port {DEFAULT_DSH_PORT} 响应'}
        time.sleep(0.5)
    return {'ok': False, 'reason': f'超时 ({timeout} 秒)'}


def save_crash_log(reason: str) -> None:
    CRASH_LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    log_file = CRASH_LOG_DIR / f'crash-{ts}.log'
    parts = ['=== DSH Crash Log ===', f'Time: {time.strftime("%Y-%m-%d %H:%M:%S")}', f'Reason: {reason}', '']
    for buf in (BOOT_LOG, BOOT_LOG_ERR):
        if buf.exists():
            parts.append(f'--- {buf.name} ---')
            parts.append(buf.read_text(encoding='utf-8', errors='replace'))
    try:
        log_file.write_text('\n'.join(parts), encoding='utf-8')
        (CRASH_LOG_DIR / 'latest.log').write_text('\n'.join(parts), encoding='utf-8')
    except Exception:
        pass
    log(f'崩溃日志已保存: {log_file}')


def enter_safe_mode(level: int, increment_crash: bool) -> None:
    log(f'========== 进入安全模式 (level {level}) ==========')
    pkg = read_json(PKG_JSON)
    if pkg is None:
        log('ERROR: 无法读取 profile package.json')
        return
    dsh = pkg.setdefault('dsh', {})
    prof = dsh.setdefault('profile', {})
    bundles = list(prof.get('bundles', []))

    # 插件全集 = 当前 bundles ∪ 上次 state ∪ 上次备份（二次升级后列表不再丢失）
    prev = read_json(STATE_FILE) or {}
    prev_all = prev.get('allBundles') or []
    prev_backup = read_json(BACKUP)
    backup_bundles = (((prev_backup or {}).get('dsh') or {}).get('profile') or {}).get('bundles') or []
    seen = set()
    all_bundles = []
    for b in bundles + list(prev_all) + list(backup_bundles):
        if b not in seen:
            seen.add(b)
            all_bundles.append(b)

    # 备份永远携带全集清单：二次崩溃不会覆盖掉原始插件列表
    pkg_backup = json.loads(json.dumps(pkg))
    pb_prof = pkg_backup.setdefault('dsh', {}).setdefault('profile', {})
    pb_prof['bundles'] = all_bundles
    write_json(BACKUP, pkg_backup)
    log('已备份 package.json -> rescue-backup（保留全部已知插件清单）')

    official_cur = [b for b in bundles if is_official(b)]
    official = [b for b in all_bundles if is_official(b)]
    whitelist = get_whitelist()
    cur_set = set(bundles)

    st = get_state()
    crash_count = st['crashCount']
    if increment_crash:
        crash_count += 1

    if level >= 2:
        keep = list(official_cur)
        whitelist_kept = []
    else:
        keep = official_cur + [w for w in whitelist if w in cur_set and not is_official(w)]
        whitelist_kept = [w for w in whitelist if w in cur_set and not is_official(w)]
    # 救砖插件自身永不被裁剪（否则升级安全模式后救援链自断，无法自愈还原 bundles）
    if 'dsh-rescue-bootloader' in cur_set and 'dsh-rescue-bootloader' not in keep:
        keep.append('dsh-rescue-bootloader')
    disabled = [b for b in all_bundles if b not in keep]

    prof['bundles'] = keep
    write_json(PKG_JSON, pkg)

    dsh_ver = get_dsh_version()
    log(f'保留官方 ({len(official_cur)}): {", ".join(official_cur)}')
    if whitelist_kept:
        log(f'保留白名单 ({len(whitelist_kept)}): {", ".join(whitelist_kept)}')
    log(f'禁用 ({len(disabled)}): {", ".join(disabled)}')
    log(f'第 #{crash_count} 次崩溃 (level {level}) - DSH version: {dsh_ver}')

    write_state({
        'safeMode': True,
        'crashCount': crash_count,
        'dshVersion': dsh_ver,
        'allBundles': all_bundles,
        'official': official,
        'whitelist': whitelist,
        'disabled': disabled,
        'port': DEFAULT_RESCUE_PORT,
    })
    CRASH_FLAG.write_text('1', encoding='utf-8')


def enter_safe_mode_for_crash() -> None:
    st = get_state()
    level = 2 if st['crashCount'] >= 1 else 1
    enter_safe_mode(level, increment_crash=True)


def kill_dsh(proc) -> None:
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            time.sleep(1)
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding='utf-8').strip())
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True, creationflags=NO_WINDOW)
        except Exception:
            pass
        PID_FILE.unlink(missing_ok=True)


# --- 简易两级流程 ---
def do_normal_boot():
    proc = launch_dsh()
    result = wait_for_startup(proc, ARGS.timeout)
    if result['ok']:
        # 稳定性检查（5 秒）
        stab_deadline = time.time() + 5
        crashed = False
        while time.time() < stab_deadline:
            if proc.poll() is not None:
                crashed = True
                break
            time.sleep(0.5)
        if crashed:
            log(f'DSH 启动后不久崩溃 (code={proc.returncode})')
            save_crash_log(f'process exited shortly after port responded (code={proc.returncode})')
            time.sleep(2)
            enter_safe_mode_for_crash()
            start_rescue_server()
            proc = launch_dsh()
            r2 = wait_for_startup(proc, ARGS.timeout)
            if not r2['ok']:
                log('安全模式启动失败，升级到仅官方...')
                kill_dsh(proc)
                time.sleep(2)
                enter_safe_mode(2, increment_crash=True)
                start_rescue_server()
                proc = launch_dsh()
                r3 = wait_for_startup(proc, ARGS.timeout)
                if r3['ok']:
                    log('严格安全模式启动成功（仅官方）')
                else:
                    log('严格安全模式也失败，核心可能损坏')
            else:
                log('安全模式启动成功（官方+白名单）')
            proc.wait()
            return
        log(f'DSH 启动成功且稳定: {result["reason"]}')
        reset_crash_state()
        log(f'DSH Web: http://127.0.0.1:{DEFAULT_DSH_PORT}')
        log(f'救砖管理台: http://127.0.0.1:{DEFAULT_RESCUE_PORT}')
        proc.wait()
    else:
        reason = result['reason']
        crashed = ('进程退出' in reason) or (proc.poll() is not None)
        if crashed:
            log(f'DSH 启动失败: {reason}')
            save_crash_log(reason)
            if proc.poll() is None:
                kill_dsh(proc)
            time.sleep(2)
            enter_safe_mode_for_crash()
            start_rescue_server()
            proc = launch_dsh()
            r2 = wait_for_startup(proc, ARGS.timeout)
            if r2['ok']:
                log('安全模式启动成功（官方+白名单）')
            else:
                log('安全模式启动失败，升级到仅官方...')
                kill_dsh(proc)
                time.sleep(2)
                enter_safe_mode(2, increment_crash=True)
                start_rescue_server()
                proc = launch_dsh()
                r3 = wait_for_startup(proc, ARGS.timeout)
                if r3['ok']:
                    log('严格安全模式启动成功（仅官方）')
                else:
                    log('严格安全模式也失败，核心可能损坏')
            proc.wait()
        else:
            log(f'启动检测超时（{reason}），但 DSH 进程仍存活——判定为慢启动而非崩溃，不进入安全模式')
            log('保留全部插件，继续监听 DSH（可 Ctrl+C 或用救砖台干预）')
            start_rescue_server()
            try:
                proc.wait()
            except Exception:
                pass


def do_safe_boot():
    st = get_state()
    level = 2 if st['crashCount'] >= 1 else 1
    enter_safe_mode(level, increment_crash=False)
    start_rescue_server()
    proc = launch_dsh()
    r2 = wait_for_startup(proc, ARGS.timeout)
    if r2['ok']:
        log('安全模式已启动（仅官方/白名单）')
    else:
        log(f'安全模式启动失败 ({r2["reason"]})，升级到仅官方...')
        kill_dsh(proc)
        time.sleep(2)
        enter_safe_mode(2, increment_crash=True)
        start_rescue_server()
        proc = launch_dsh()
        r3 = wait_for_startup(proc, ARGS.timeout)
        if r3['ok']:
            log('严格安全模式启动成功（仅官方）')
        else:
            log('严格安全模式也失败，核心可能损坏')
    proc.wait()


ARGS = None


def main():
    global ARGS, PROFILE_DIR, DEFAULT_DSH_PORT, DEFAULT_RESCUE_PORT, PKG_JSON, BACKUP
    p = argparse.ArgumentParser(description='DSH 救砖启动器 (Python)')
    p.add_argument('--safe', action='store_true', help='强制进入安全模式')
    p.add_argument('--timeout', type=int, default=300, help='启动检测超时(秒)')
    p.add_argument('--dsh-port', type=int, default=DEFAULT_DSH_PORT, help='DSH 端口')
    p.add_argument('--rescue-port', type=int, default=DEFAULT_RESCUE_PORT, help='救砖管理台端口')
    p.add_argument('--daemon', action='store_true', help='守护模式：启动器也脱离控制台，全程后台运行')
    p.add_argument('--profile', default=str(PROFILE_DIR), help='profile 目录')
    ARGS = p.parse_args()

    PROFILE_DIR = Path(ARGS.profile)
    DEFAULT_DSH_PORT = ARGS.dsh_port
    DEFAULT_RESCUE_PORT = ARGS.rescue_port

    PKG_JSON = PROFILE_DIR / 'package.json'
    BACKUP = PROFILE_DIR / 'package.json.rescue-backup'

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log('DSH Rescue Bootloader v1.1.4 (Python)')
    log(f'Profile: {PROFILE_DIR}')
    log(f'DSH 版本: {get_dsh_version()}')


    # 守护模式：重新以脱离控制台的方式启动自己，然后退出（DSH 与监控都后台运行）
    if ARGS.daemon and not os.environ.get('DSH_RESCUE_DAEMON'):
        log('切换到守护模式（脱离控制台）...')
        env = dict(os.environ)
        env['DSH_RESCUE_DAEMON'] = '1'
        flags = 0
        if os.name == 'nt':
            flags = (getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                     | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                     | 0x00000008)
        args = ['--daemon', '--dsh-port', str(DEFAULT_DSH_PORT), '--rescue-port', str(DEFAULT_RESCUE_PORT),
                '--profile', str(PROFILE_DIR), '--timeout', str(ARGS.timeout)]
        if ARGS.safe:
            args.append('--safe')
        try:
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve())] + args,
                cwd=str(PLUGIN_DIR), env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except Exception as e:
            log(f'守护启动失败: {e}')
        log(f'已在后台启动 DSH：http://127.0.0.1:{DEFAULT_DSH_PORT}（救砖管理台 http://127.0.0.1:{DEFAULT_RESCUE_PORT}）')
        return

    force_safe = ARGS.safe or CRASH_FLAG.exists()

    if force_safe:
        log('崩溃标记/--safe 存在，进入安全模式')
        do_safe_boot()
    else:
        log('正常启动，进行监控...')
        do_normal_boot()


if __name__ == '__main__':
    main()