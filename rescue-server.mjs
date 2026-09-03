// DSH 救砖管理台 — 零依赖 Node.js HTTP 服务器
// 用法: node rescue-server.mjs <port> <profileDir>
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { exec } from 'node:child_process';

const PORT = parseInt(process.argv[2] || '8105', 10);
const PROFILE_DIR = process.argv[3] || path.join(process.env.USERPROFILE || '.', '.dsh', 'profiles', 'web');
const RESCUE_DIR = process.argv[4] || path.join(process.env.USERPROFILE || '.', '.dsh', 'rescue');
const PKG_JSON = path.join(PROFILE_DIR, 'package.json');
const BACKUP = path.join(PROFILE_DIR, 'package.json.rescue-backup');
const STATE_FILE = path.join(RESCUE_DIR, 'state.json');
const CRASH_FLAG = path.join(RESCUE_DIR, '.crash-flag');
const WHITELIST_FILE = path.join(RESCUE_DIR, 'whitelist.json');
const CRASH_LOG_DIR = path.join(RESCUE_DIR, 'crash-logs');

function isOfficial(name) {
  return name.startsWith('@deepseek-ai/');
}

function readJson(file) {
  let txt = fs.readFileSync(file, 'utf8');
  if (txt.charCodeAt(0) === 0xFEFF) txt = txt.slice(1); // strip BOM
  return JSON.parse(txt);
}

function writeJson(file, obj) {
  fs.writeFileSync(file, JSON.stringify(obj, null, 2) + '\n', 'utf8');
}

function getWhitelist() {
  try {
    if (fs.existsSync(WHITELIST_FILE)) {
      const wl = readJson(WHITELIST_FILE);
      if (Array.isArray(wl)) return wl;
      if (typeof wl === 'string') return [wl];
    }
  } catch {}
  return [];
}

function writeWhitelist(arr) {
  writeJson(WHITELIST_FILE, arr);
}

function getCrashLog() {
  const latest = path.join(CRASH_LOG_DIR, 'latest.log');
  try {
    if (fs.existsSync(latest)) {
      return fs.readFileSync(latest, 'utf8');
    }
  } catch {}
  // List available crash logs
  try {
    if (fs.existsSync(CRASH_LOG_DIR)) {
      const files = fs.readdirSync(CRASH_LOG_DIR).filter(f => f.startsWith('crash-')).sort().reverse();
      if (files.length > 0) {
        return fs.readFileSync(path.join(CRASH_LOG_DIR, files[0]), 'utf8');
      }
    }
  } catch {}
  return null;
}

function getCurrentState() {
  let allBundles = [];
  let official = [];
  let disabled = [];
  let safeMode = false;

  try {
    if (fs.existsSync(STATE_FILE)) {
      const st = readJson(STATE_FILE);
      allBundles = st.allBundles || [];
      official = st.official || [];
      disabled = st.disabled || [];
      safeMode = !!st.safeMode;
    }
  } catch {}

  const whitelist = getWhitelist();

  let currentBundles = [];
  try {
    const pkg = readJson(PKG_JSON);
    currentBundles = pkg.dsh?.profile?.bundles || [];
  } catch {}

  // 正常模式下（无 state.json），从当前 package.json 推导 allBundles 和 official
  if (allBundles.length === 0 && currentBundles.length > 0) {
    allBundles = currentBundles;
    official = currentBundles.filter(b => isOfficial(b));
  }

  const enabledThirdParty = currentBundles.filter(b => !isOfficial(b));
  const currentDisabled = allBundles.filter(b => !currentBundles.includes(b));

  return {
    safeMode,
    allBundles,
    official,
    whitelist,
    enabledThirdParty,
    disabled: currentDisabled,
    currentBundles,
  };
}

function restartDsh() {
  // Only kill dsh processes (NOT the rescue server itself)
  const killCmd = `powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\\"Name='node.exe'\\\" | Where-Object { $_.CommandLine -match 'dsh' -and $_.CommandLine -notmatch 'rescue-server' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"`;
  exec(killCmd, () => {
    setTimeout(() => {
      // dsh-rescue.ps1 位于插件根目录（与本文件同级）
      const rescuePs = path.join(import.meta.dirname, 'dsh-rescue.ps1');
      exec(`powershell -NoProfile -ExecutionPolicy Bypass -File "${rescuePs}"`, () => {});
    }, 2500);
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  // GET / -> 管理台 UI
  if (url.pathname === '/' && req.method === 'GET') {
    const html = fs.readFileSync(path.join(import.meta.dirname, 'rescue-ui.html'), 'utf8');
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.writeHead(200);
    res.end(html);
    return;
  }

  // GET /api/state
  if (url.pathname === '/api/state' && req.method === 'GET') {
    res.writeHead(200);
    res.end(JSON.stringify(getCurrentState()));
    return;
  }

  // POST /api/apply — 重新启用选中的插件（官方 + 白名单 + 选中）
  if (url.pathname === '/api/apply' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) body += chunk;
    const { enable } = JSON.parse(body || '{}');
    const toEnable = Array.isArray(enable) ? enable : [];

    const state = getCurrentState();
    // 新的 bundles = 官方 + 白名单 + 选中启用的
    const newBundles = [...state.official, ...state.whitelist, ...toEnable];

    try {
      const pkg = readJson(PKG_JSON);
      pkg.dsh.profile.bundles = newBundles;
      writeJson(PKG_JSON, pkg);
      // 清除崩溃标记，使重启后走正常启动流程
      fs.rmSync(CRASH_FLAG, { force: true });
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, message: `已启用 ${toEnable.length} 个插件（官方+白名单保留），正在重启 DSH...` }));
      restartDsh();
    } catch (e) {
      res.writeHead(500);
      res.end(JSON.stringify({ ok: false, message: e.message }));
    }
    return;
  }

  // POST /api/whitelist — 切换插件白名单状态 { name, action: 'add'|'remove' }
  if (url.pathname === '/api/whitelist' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) body += chunk;
    const { name, action } = JSON.parse(body || '{}');
    if (!name) { res.writeHead(400); res.end(JSON.stringify({ ok: false, message: 'name required' })); return; }
    try {
      let wl = getWhitelist();
      if (action === 'remove') {
        wl = wl.filter(w => w !== name);
      } else {
        if (!wl.includes(name)) wl.push(name);
      }
      writeWhitelist(wl);
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, whitelist: wl, message: action === 'remove' ? `已从白名单移除 ${name}` : `已加入白名单 ${name}` }));
    } catch (e) {
      res.writeHead(500);
      res.end(JSON.stringify({ ok: false, message: e.message }));
    }
    return;
  }

  // GET /api/crash-log — 获取最近一次崩溃日志
  if (url.pathname === '/api/crash-log' && req.method === 'GET') {
    const log = getCrashLog();
    res.writeHead(200);
    res.end(JSON.stringify({ ok: true, log: log || '暂无崩溃日志' }));
    return;
  }

  // DELETE /api/crash-log — 清除所有崩溃日志
  if (url.pathname === '/api/crash-log' && req.method === 'DELETE') {
    try {
      if (fs.existsSync(CRASH_LOG_DIR)) {
        const files = fs.readdirSync(CRASH_LOG_DIR);
        files.forEach(f => {
          if (f.startsWith('crash-')) fs.rmSync(path.join(CRASH_LOG_DIR, f), { force: true });
        });
        fs.rmSync(path.join(CRASH_LOG_DIR, 'latest.log'), { force: true });
      }
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, message: '崩溃日志已清除' }));
    } catch (e) {
      res.writeHead(500);
      res.end(JSON.stringify({ ok: false, message: e.message }));
    }
    return;
  }

  // POST /api/restore — 恢复全部插件（退出安全模式）
  if (url.pathname === '/api/restore' && req.method === 'POST') {
    try {
      if (fs.existsSync(BACKUP)) {
        fs.copyFileSync(BACKUP, PKG_JSON);
      }
      fs.rmSync(CRASH_FLAG, { force: true });
      fs.rmSync(STATE_FILE, { force: true });
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, message: '已恢复全部插件，正在重启 DSH...' }));
      restartDsh();
    } catch (e) {
      res.writeHead(500);
      res.end(JSON.stringify({ ok: false, message: e.message }));
    }
    return;
  }

  // POST /api/restart — 仅重启 DSH
  if (url.pathname === '/api/restart' && req.method === 'POST') {
    res.writeHead(200);
    res.end(JSON.stringify({ ok: true, message: '正在重启 DSH...' }));
    restartDsh();
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ ok: false, message: 'Not found' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[rescue] 管理台已启动: http://127.0.0.1:${PORT}`);
});
