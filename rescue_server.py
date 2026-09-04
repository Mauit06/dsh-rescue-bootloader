#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DSH 救砖管理台后端（Python，替代 rescue-server.mjs）

用法: python rescue_server.py <port> <profileDir> <rescueDir>
纯标准库 HTTP 服务器，serve rescue-ui.html + /api/*。
"""
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# Windows：子进程无控制台窗口
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8105
PROFILE_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / '.dsh' / 'profiles' / 'web'
RESCUE_DIR = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.home() / '.dsh' / 'rescue'

PKG_JSON = PROFILE_DIR / 'package.json'
BACKUP = PROFILE_DIR / 'package.json.rescue-backup'
STATE_FILE = RESCUE_DIR / 'state.json'
CRASH_FLAG = RESCUE_DIR / '.crash-flag'
WHITELIST_FILE = RESCUE_DIR / 'whitelist.json'
CRASH_LOG_DIR = RESCUE_DIR / 'crash-logs'
PID_FILE = RESCUE_DIR / 'dsh.pid'
PLUGIN_DIR = Path(__file__).resolve().parent
UI_HTML = PLUGIN_DIR / 'rescue-ui.html'
LAUNCHER = PLUGIN_DIR / 'dsh_rescue.py'

OFFICIAL_PREFIX = '@deepseek-ai/'


def is_official(name: str) -> bool:
    return name.startswith(OFFICIAL_PREFIX)


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        txt = path.read_text(encoding='utf-8')
        if txt.startswith('\ufeff'):
            txt = txt[1:]
        return json.loads(txt)
    except Exception:
        return None


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def get_whitelist() -> list:
    wl = read_json(WHITELIST_FILE)
    if isinstance(wl, list):
        return wl
    if isinstance(wl, str):
        return [wl]
    return []


def write_whitelist(arr) -> None:
    write_json(WHITELIST_FILE, arr)


def get_crash_log():
    latest = CRASH_LOG_DIR / 'latest.log'
    if latest.exists():
        try:
            return latest.read_text(encoding='utf-8', errors='replace')
        except Exception:
            pass
    if CRASH_LOG_DIR.exists():
        files = sorted([f for f in CRASH_LOG_DIR.iterdir() if f.name.startswith('crash-') and f.is_file()], reverse=True)
        if files:
            try:
                return files[0].read_text(encoding='utf-8', errors='replace')
            except Exception:
                pass
    return None


def get_dsh_version() -> str:
    try:
        pkg = read_json(PKG_JSON)
        deps = (pkg or {}).get('dependencies', {}) or {}
        for k in ('@deepseek-ai/dsh-web-app', '@deepseek-ai/dsh', '@deepseek-ai/dsh-base'):
            if deps.get(k):
                return str(deps[k])
    except Exception:
        pass
    return 'unknown'


def _dedupe(xs):
    seen = set()
    out = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def bundle_universe(current_bundles=None, state=None):
    """插件全集：当前 bundles ∪ state.allBundles ∪ 备份 bundles ∪ 白名单 ∪ 第三方依赖。
    即使旧版本逻辑把 state/backup 写坏（二次升级后列表丢失），依赖表仍能让清单复原。"""
    pkg = read_json(PKG_JSON) or {}
    if current_bundles is None:
        current_bundles = ((pkg.get('dsh') or {}).get('profile') or {}).get('bundles', []) or []
    st = state if state is not None else (read_json(STATE_FILE) or {})
    backup = read_json(BACKUP) or {}
    backup_bundles = ((backup.get('dsh') or {}).get('profile') or {}).get('bundles', []) or []
    deps = [k for k in (pkg.get('dependencies') or {}).keys() if not is_official(k)]
    return _dedupe(list(current_bundles) + list(st.get('allBundles') or [])
                   + list(backup_bundles) + list(get_whitelist()) + deps)


def get_current_state() -> dict:
    st = read_json(STATE_FILE) or {}
    safe_mode = bool(st.get('safeMode'))
    crash_count = int(st.get('crashCount') or 0)
    stored_version = st.get('dshVersion') or ''

    whitelist = get_whitelist()
    pkg = read_json(PKG_JSON) or {}
    current_bundles = ((pkg.get('dsh') or {}).get('profile') or {}).get('bundles', []) or []

    all_bundles = bundle_universe(current_bundles, st)
    official = [b for b in all_bundles if is_official(b)]
    enabled_third_party = [b for b in current_bundles if not is_official(b)]
    current_disabled = [b for b in all_bundles if b not in current_bundles]

    return {
        'safeMode': safe_mode,
        'crashCount': crash_count,
        'dshVersion': stored_version or get_dsh_version(),
        'allBundles': all_bundles,
        'official': official,
        'whitelist': whitelist,
        'enabledThirdParty': enabled_third_party,
        'disabled': current_disabled,
        'currentBundles': current_bundles,
    }


def restart_dsh() -> None:
    # 杀掉 DSH（通过 PID 文件，精确，不误杀其它 node 进程）
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding='utf-8').strip())
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True, creationflags=NO_WINDOW)
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except Exception:
            pass
    time.sleep(1.5)
    # 重新启动 launcher（后台，不阻塞）
    try:
        subprocess.Popen(
            [sys.executable, str(LAUNCHER)],
            cwd=str(PLUGIN_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
    except Exception:
        pass


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            try:
                html = UI_HTML.read_text(encoding='utf-8')
                body = html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception:
                self._send({'ok': False, 'message': 'UI not found'}, 404)
                return
        if path == '/api/state':
            self._send(get_current_state())
            return
        if path == '/api/crash-log':
            self._send({'ok': True, 'log': get_crash_log() or '暂无崩溃日志'})
            return
        self._send({'ok': False, 'message': 'Not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()
        if path == '/api/apply':
            enable = body.get('enable', [])
            to_enable = enable if isinstance(enable, list) else []
            state = get_current_state()
            new_bundles = state['official'] + state['whitelist'] + to_enable
            try:
                pkg = read_json(PKG_JSON)
                pkg['dsh']['profile']['bundles'] = new_bundles
                write_json(PKG_JSON, pkg)
                CRASH_FLAG.unlink(missing_ok=True)
                if STATE_FILE.exists():
                    STATE_FILE.unlink()
                self._send({'ok': True, 'message': f'已启用 {len(to_enable)} 个插件（官方+白名单保留），正在重启 DSH...'})
                restart_dsh()
            except Exception as e:
                self._send({'ok': False, 'message': str(e)}, 500)
            return
        if path == '/api/whitelist':
            name = body.get('name')
            action = body.get('action')
            if not name:
                self._send({'ok': False, 'message': 'name required'}, 400)
                return
            wl = get_whitelist()
            if action == 'remove':
                wl = [w for w in wl if w != name]
            elif name not in wl:
                wl.append(name)
            write_whitelist(wl)
            self._send({'ok': True, 'whitelist': wl, 'message': f'已从白名单移除 {name}' if action == 'remove' else f'已加入白名单 {name}'})
            return
        if path == '/api/restore':
            try:
                if BACKUP.exists():
                    PKG_JSON.write_bytes(BACKUP.read_bytes())
                else:
                    pkg = read_json(PKG_JSON)
                    if not isinstance(pkg, dict):
                        raise RuntimeError('package.json 不可读')
                    pkg.setdefault('dsh', {}).setdefault('profile', {})['bundles'] = bundle_universe()
                    write_json(PKG_JSON, pkg)
                CRASH_FLAG.unlink(missing_ok=True)
                if STATE_FILE.exists():
                    STATE_FILE.unlink()
                self._send({'ok': True, 'message': '已恢复全部插件，正在重启 DSH...'})
                restart_dsh()
            except Exception as e:
                self._send({'ok': False, 'message': str(e)}, 500)
            return
        if path == '/api/restart':
            self._send({'ok': True, 'message': '正在重启 DSH...'})
            restart_dsh()
            return
        self._send({'ok': False, 'message': 'Not found'}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == '/api/crash-log':
            try:
                if CRASH_LOG_DIR.exists():
                    for f in CRASH_LOG_DIR.iterdir():
                        if f.is_file() and f.name.startswith('crash-'):
                            f.unlink()
                    (CRASH_LOG_DIR / 'latest.log').unlink(missing_ok=True)
                self._send({'ok': True, 'message': '崩溃日志已清除'})
            except Exception as e:
                self._send({'ok': False, 'message': str(e)}, 500)
            return
        self._send({'ok': False, 'message': 'Not found'}, 404)


class RescueHTTPServer(ThreadingHTTPServer):
    # Windows 上 SO_REUSEADDR 允许重复绑定同一端口（多实例抢流）。
    # 关闭它：第二个实例直接 bind 失败退出，保证管理台单实例。
    allow_reuse_address = False


def main():
    RESCUE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        server = RescueHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError:
        print(f'[rescue] 端口 {PORT} 已被另一实例占用，本实例退出', flush=True)
        return
    print(f'[rescue] 管理台已启动: http://127.0.0.1:{PORT}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
