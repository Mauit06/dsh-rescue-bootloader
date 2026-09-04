/**
 * dsh-rescue-bootloader — DSH 救砖模块（Python 实现，v1.1.1 起一条命令安装/卸载）
 *
 * JS 入口只做三件事（cordis 契约要求插件入口为 JS）：
 *   1. 自安装：插件加载时自动把「崩溃检测拦截」写入全局 dsh 包装脚本
 *      （dsh.cmd / dsh.ps1 / POSIX dsh shim），使后续 dsh web（含 dsh --profile web）
 *      转交 dsh_rescue.py。幂等、可升级旧版补丁、写前自动备份 .dsh-rescue-bak。
 *   2. 拉起救砖管理台 rescue_server.py（http://127.0.0.1:8105）。
 *   3. 自卸载：插件被移除（dsh plugin remove）或 DSH 退出时，自动还原全部包装脚本。
 *
 * 安装：dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
 * 卸载：dsh plugin --profile web remove dsh-rescue-bootloader
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync, copyFileSync, unlinkSync, mkdirSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import { fileURLToPath } from 'node:url';

const name = 'rescue-bootloader';
const inject = [];

const RESCUE_PORT = 8105;
const PLUGIN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SERVER_SCRIPT = path.join(PLUGIN_ROOT, 'rescue_server.py');
const LAUNCHER = path.join(PLUGIN_ROOT, 'dsh_rescue.py');
const UNINSTALLER = path.join(PLUGIN_ROOT, 'uninstall.py');
const RESCUE_DIR = path.join(PLUGIN_ROOT, 'data');
const PROFILE_DIR = path.join(os.homedir(), '.dsh', 'profiles', 'web');
const STANDALONE = path.join(os.homedir(), '.dsh', 'dsh-rescue-uninstall.py');
const MARKER = '=== DSH Rescue: intercept web subcommand ===';
const END = '=== DSH Rescue: end ===';
const SIG = /node_modules[/\\]@deepseek-ai[/\\]dsh/;

function log(...args) {
  console.log('[rescue-bootloader]', ...args);
}

function isPortInUse(port) {
  return new Promise((resolve) => {
    const tester = net.createConnection({ port, host: '127.0.0.1' });
    const done = (v) => { clearTimeout(timer); try { tester.destroy(); } catch {} resolve(v); };
    const timer = setTimeout(() => done(false), 1500);
    tester.once('connect', () => done(true));
    tester.once('error', () => done(false));
  });
}

// ---------- Python 发现（结果缓存为全路径，不依赖 PATH） ----------
function pythonWorks(cmd, prefix) {
  try {
    const r = spawnSync(cmd, prefix.concat(['-c', 'import sys;print(1)']), { timeout: 15000, encoding: 'utf8', windowsHide: true });
    return !r.error && String(r.stdout || '').trim() === '1';
  } catch { return false; }
}

function discoverPython() {
  const cache = path.join(RESCUE_DIR, 'python.path');
  if (existsSync(cache)) {
    try {
      const v = readFileSync(cache, 'utf8').trim();
      if (v && existsSync(v) && pythonWorks(v, [])) return { cmd: v, prefix: [] };
    } catch {}
  }
  const cands = process.platform === 'win32'
    ? [['python', []], ['py', ['-3']], ['python3', []]]
    : [['python3', []], ['python', []]];
  for (const item of cands) {
    const cmd = item[0], prefix = item[1];
    if (!pythonWorks(cmd, prefix)) continue;
    let exe = '';
    try {
      const r = spawnSync(cmd, prefix.concat(['-c', 'import sys;print(sys.executable)']), { timeout: 15000, encoding: 'utf8', windowsHide: true });
      exe = String(r.stdout || '').trim();
    } catch {}
    const resolved = (exe && existsSync(exe)) ? { cmd: exe, prefix: [] } : { cmd, prefix };
    try {
      mkdirSync(RESCUE_DIR, { recursive: true });
      writeFileSync(cache, resolved.cmd, 'utf8');
    } catch {}
    return resolved;
  }
  return null;
}

// ---------- 全局 dsh 包装脚本定位 ----------
function shimDirs() {
  const dirs = [];
  try { dirs.push(path.dirname(process.execPath)); } catch {}
  if (process.env.APPDATA) dirs.push(path.join(process.env.APPDATA, 'npm'));
  if (process.platform === 'win32') {
    dirs.push(path.join(os.homedir(), 'AppData', 'Roaming', 'npm'));
  } else {
    dirs.push(path.join(os.homedir(), '.npm-global', 'bin'), '/usr/local/bin', '/opt/homebrew/bin');
  }
  return Array.from(new Set(dirs.filter(Boolean)));
}

function findShims() {
  const out = [];
  for (const d of shimDirs()) {
    for (const f of ['dsh.cmd', 'dsh.ps1', 'dsh']) {
      const p = path.join(d, f);
      if (existsSync(p) && out.indexOf(p) < 0) out.push(p);
    }
  }
  return out;
}

// ---------- 拦截块生成 / 移除 ----------
function eolOf(c) { return c.indexOf('\r\n') >= 0 ? '\r\n' : '\n'; }

function invCmd(py, script) {
  return ['"' + py.cmd + '"'].concat(py.prefix).concat(['"' + script + '"']).join(' ');
}

function blockCmd(py, script, eol) {
  // 严格位置判定：仅 dsh web / dsh --profile web 进入救援；
  // dsh plugin --profile web … 等含 web 的子命令一律放行（修复 WebUI 操作误触发闪窗）。
  return [
    'REM ' + MARKER,
    'if "%~1"=="web" goto dshrescue',
    'if "%~1"=="--profile" if "%~2"=="web" goto dshrescue',
    'goto rundsh',
    ':dshrescue',
    'if not EXIST "' + script + '" goto rundsh',
    'endLocal',
    invCmd(py, script),
    'exit /b %ERRORLEVEL%',
    ''
  ].join(eol);
}

function blockPs(py, script, eol) {
  const pre = py.prefix.length ? ' ' + py.prefix.map((q) => "'" + q + "'").join(' ') : '';
  return [
    '# ' + MARKER,
    "if ($args[0] -eq 'web' -or ($args[0] -eq '--profile' -and $args[1] -eq 'web')) {",
    "  $rescuePs = '" + script + "'",
    '  if (Test-Path $rescuePs) {',
    "    & '" + py.cmd + "'" + pre + ' $rescuePs',
    '    exit $LASTEXITCODE',
    '  }',
    '}',
    '# ' + END,
    ''
  ].join(eol);
}

function blockSh(py, script, eol) {
  const pre = py.prefix.length ? ' ' + py.prefix.join(' ') : '';
  return [
    '# ' + MARKER,
    'if [ "$1" = "web" ] || { [ "$1" = "--profile" ] && [ "$2" = "web" ]; }; then',
    '  if [ -f "' + script + '" ]; then exec "' + py.cmd + '"' + pre + ' "' + script + '"; fi',
    'fi',
    '# ' + END,
    ''
  ].join(eol);
}

// 移除批处理拦截块：从 REM 标记行到 exit /b %ERRORLEVEL% 行（块体自界定，不依赖标签）；
// 并修复历史损坏（若 :rundsh 标签丢失，则在 npm 执行行前补回）。返回 null 表示无法安全处理。
function stripCmdBlock(c) {
  for (let guard = 0; guard < 10; guard++) {
    const i = c.indexOf('REM ' + MARKER);
    if (i < 0) break;
    const x = c.indexOf('exit /b %ERRORLEVEL%', i);
    if (x < 0) return null;
    let end = c.indexOf('\n', x);
    end = end < 0 ? c.length : end + 1;
    c = c.slice(0, i) + c.slice(end);
  }
  // 修复历史损坏：若标签与下一命令粘连（:rundshendLocal...），先拆开
  const fi = c.indexOf(':rundsh');
  if (fi >= 0) {
    const after = c[fi + ':rundsh'.length];
    if (after && after !== '\r' && after !== '\n') {
      c = c.slice(0, fi + ':rundsh'.length) + '\r\n' + c.slice(fi + ':rundsh'.length);
    }
  }
  if (c.indexOf(':rundsh') < 0) {
    const anchor = c.indexOf('endLocal & goto #_undefined_#');
    if (anchor < 0) return null;
    const head = c.slice(0, anchor);
    const trail = c.slice(anchor);
    if (head.endsWith('\r\n') || head.endsWith('\n')) c = head + ':rundsh\r\n' + trail;
    else if (head === '') c = ':rundsh\r\n' + trail;
    else return null; // 无法确定行尾风格，保守跳过
  }
  return c;
}

// 移除 # 注释式拦截块（新格式带 end 标记；兼容旧格式=到首个空行）
function stripMarkerBlock(c) {
  for (let guard = 0; guard < 10; guard++) {
    const i = c.indexOf('# === DSH Rescue:'); // 前缀匹配：含历史变体/乱码注释块
    if (i < 0) return c;
    let end;
    if (c.startsWith('# ' + END, i)) {
      const n = c.indexOf('\n', i);
      end = n < 0 ? c.length : n + 1; // 孤立的 end 行
    } else {
      const e = c.indexOf('# ' + END, i);
      if (e >= 0) {
        const n = c.indexOf('\n', e);
        end = n < 0 ? c.length : n + 1;
      } else {
        const a = c.indexOf('\n\n', i);
        const b = c.indexOf('\r\n\r\n', i);
        let n = -1;
        if (a >= 0 && b >= 0) n = Math.min(a, b);
        else if (a >= 0) n = a;
        else n = b;
        if (n < 0) return null;
        end = (c[n] === '\r') ? n + 4 : n + 2;
      }
    }
    c = c.slice(0, i) + c.slice(end);
  }
  return c;
}

function insertCmd(stripped, block) {
  const k = stripped.indexOf(':rundsh');
  if (k < 0) return null;
  const head = stripped.slice(0, k);
  if (k > 0 && !head.endsWith('\n')) return null; // 标签前必须是行首
  return head + block + stripped.slice(k);
}

function insertPs(stripped, block, eol) {
  const i = stripped.indexOf('$basedir=');
  if (i >= 0) {
    const n = stripped.indexOf('\n', i);
    if (n >= 0) return stripped.slice(0, n + 1) + block + stripped.slice(n + 1);
  }
  return block + eol + stripped;
}

function insertSh(stripped, block) {
  if (stripped.startsWith('#!')) {
    const n = stripped.indexOf('\n');
    if (n >= 0) return stripped.slice(0, n + 1) + block + stripped.slice(n + 1);
  }
  return block + stripped;
}

function kindOf(p) {
  const b = path.basename(p);
  return b.endsWith('.cmd') ? 'cmd' : (b.endsWith('.ps1') ? 'ps1' : 'sh');
}

// 把一个包装脚本规范化为“恰好一份最新拦截块”（幂等升级）
function normalizeShim(p, py) {
  const kind = kindOf(p);
  const raw = readFileSync(p, 'utf8');
  const eol = eolOf(raw);
  const stripped = kind === 'cmd' ? stripCmdBlock(raw) : stripMarkerBlock(raw);
  if (stripped === null) return { skipped: true, reason: '无法安全移除旧拦截块' };
  const block = kind === 'cmd' ? blockCmd(py, LAUNCHER, eol)
    : kind === 'ps1' ? blockPs(py, LAUNCHER, eol)
    : blockSh(py, LAUNCHER, eol);
  const next = kind === 'cmd' ? insertCmd(stripped, block)
    : kind === 'ps1' ? insertPs(stripped, block, eol)
    : insertSh(stripped, block);
  if (!next) return { skipped: true, reason: '无法定位插入点' };
  if (kind === 'cmd' && next.indexOf('\r\n:rundsh\r\n') < 0 && next.indexOf(':rundsh\r\n') < 0) return { skipped: true, reason: ':rundsh 标签结构异常' };
  if (next.indexOf(MARKER) !== next.lastIndexOf(MARKER)) return { skipped: true, reason: '拦截块重复' };
  if (next === raw) return { changed: false };
  try {
    const bak = p + '.dsh-rescue-bak';
    if (!existsSync(bak)) copyFileSync(p, bak);
  } catch {}
  writeFileSync(p, next, 'utf8');
  return { changed: true };
}

function installInterception() {
  const shims = findShims();
  if (!shims.length) { log('未找到 dsh 包装脚本，跳过自动拦截'); return []; }
  const py = discoverPython();
  if (!py) { log('未找到可用的 Python（python/python3/py），跳过自动拦截'); return []; }
  const results = [];
  for (const p of shims) {
    try {
      const c = readFileSync(p, 'utf8');
      const mine = c.indexOf(MARKER) >= 0;
      if (!mine && !SIG.test(c)) continue; // 不是 npm 的 dsh 包装（避免误伤系统同名程序）
      results.push({ file: p, kind: kindOf(p), ...normalizeShim(p, py) });
    } catch (e) { log('处理失败', p, e.message); }
  }
  try {
    if (existsSync(UNINSTALLER)) {
      mkdirSync(path.dirname(STANDALONE), { recursive: true });
      copyFileSync(UNINSTALLER, STANDALONE);
    }
  } catch {}
  for (const r of results) {
    if (r.skipped) log('跳过', r.file, '(' + r.reason + ')');
    else if (r.changed) log('已安装/升级崩溃检测拦截:', r.file);
  }
  if (results.length && !results.some((r) => r.changed)) log('崩溃检测拦截已是最新');
  return results;
}

function uninstallInterception() {
  let touched = 0;
  for (const p of findShims()) {
    try {
      const c = readFileSync(p, 'utf8');
      if (c.indexOf(MARKER) < 0) continue;
      const kind = kindOf(p);
      const stripped = kind === 'cmd' ? stripCmdBlock(c) : stripMarkerBlock(c);
      if (!stripped || stripped === c || stripped.indexOf(MARKER) >= 0) continue;
      if (kind === 'cmd' && stripped.indexOf(':rundsh') < 0) continue;
      writeFileSync(p, stripped, 'utf8');
      touched++;
      log('已还原 dsh 包装脚本:', p);
    } catch {}
  }
  try { if (existsSync(STANDALONE)) unlinkSync(STANDALONE); } catch {}
  return touched;
}

function startRescueServer(py) {
  if (!existsSync(SERVER_SCRIPT)) { log('缺少 rescue_server.py，跳过'); return null; }
  const child = spawn(py.cmd, py.prefix.concat([SERVER_SCRIPT, String(RESCUE_PORT), PROFILE_DIR, RESCUE_DIR]), {
    detached: true, stdio: 'ignore', cwd: PLUGIN_ROOT, windowsHide: true,
  });
  child.unref();
  log('rescue server 已启动 http://127.0.0.1:' + RESCUE_PORT);
  return child;
}

function apply(ctx) {
  let server = null;
  ctx.effect(async () => {
    try { installInterception(); } catch (e) { log('自动拦截安装失败:', e.message); }
    const py = discoverPython();
    const inUse = await isPortInUse(RESCUE_PORT);
    if (inUse) log('rescue server 已在端口 ' + RESCUE_PORT + ' 运行');
    else if (py) server = startRescueServer(py);
    else log('未找到 Python，救援服务器未启动');
    return () => {
      try { uninstallInterception(); } catch (e) { log('还原拦截失败:', e.message); }
      if (server) { try { if (server.exitCode === null) server.kill(); } catch {} server = null; }
    };
  }, 'rescue-bootloader: 自安装拦截 + 救援服务器');
}

const _internals = {
  discoverPython, findShims, kindOf, eolOf,
  blockCmd, blockPs, blockSh,
  stripCmdBlock, stripMarkerBlock,
  insertCmd, insertPs, insertSh,
  normalizeShim, installInterception, uninstallInterception,
  MARKER, END, LAUNCHER,
};

export { apply, inject, name, _internals };