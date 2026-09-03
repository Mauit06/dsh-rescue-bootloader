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


def get_current_state() -> dict:
    all_bundles = []
    official = []
    disabled = []
    safe_mode = False
    crash_count = 0
    stored_version = ''

    st = read_json(STATE_FILE)
    if st:
        all_bundles = st.get('allBundles', [])
        official = st.get('official', [])
        disabled = st.get('disabled', [])
        safe_mode = bool(st.get('safeMode'))
        crash_count = int(st.get('crashCount') or 0)
        stored_version = st.get('dshVersion') or ''

    whitelist = get_whitelist()
    current_bundles = []
    try:
        pkg = read_json(PKG_JSON)
        current_bundles = (pkg or {}).get('dsh', {}).get('profile', {}).get('bundles', [])
    except Exception:
        pass

    if not all_bundles and current_bundles:
        all_bundles = current_bundles
        official = [b for b in current_bundles if is_official(b)]

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
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
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


def main():
    RESCUE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print(f'[rescue] 管理台已启动: http://127.0.0.1:{PORT}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
