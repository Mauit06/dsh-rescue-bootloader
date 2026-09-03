/**
 * dsh-rescue-Bootloader — DSH 救砖管理台（一体化插件）
 *
 * 插件自带 rescue-server.mjs 和 rescue-ui.html，
 * DSH 启动时自动拉起救砖管理台 (http://127.0.0.1:8105)。
 *
 * 崩溃检测仍由外部 dsh-rescue.ps1 包装启动（必须在 DSH 之前运行）。
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import net from 'node:net';
import { fileURLToPath } from 'node:url';

const name = 'rescue-bootloader';
const inject = [];

const RESCUE_PORT = 8105;
const PROFILE_DIR = path.join(homedir(), '.dsh', 'profiles', 'web');
// rescue-server.mjs 与 rescue-ui.html 位于插件根目录
const PLUGIN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SERVER_SCRIPT = path.join(PLUGIN_ROOT, 'rescue-server.mjs');
// 数据目录：插件内 data/
const RESCUE_DIR = path.join(PLUGIN_ROOT, 'data');

/** 检查端口是否已被占用（rescue server 已在运行） */
function isPortInUse(port) {
  return new Promise((resolve) => {
    const tester = net.createConnection({ port, host: '127.0.0.1' });
    tester.once('connect', () => { tester.end(); resolve(true); });
    tester.once('error', () => resolve(false));
    setTimeout(() => { tester.destroy(); resolve(false); }, 1500);
  });
}

/** 启动 rescue-server 子进程 */
function startRescueServer() {
  if (!existsSync(SERVER_SCRIPT)) {
    console.warn(`[rescue-bootloader] rescue-server.mjs not found at ${SERVER_SCRIPT}`);
    return null;
  }
  const child = spawn('node', [SERVER_SCRIPT, String(RESCUE_PORT), PROFILE_DIR, RESCUE_DIR], {
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
  console.log(`[rescue-bootloader] rescue server started on http://127.0.0.1:${RESCUE_PORT}`);
  return child;
}

function apply(ctx) {
  let child = null;

  ctx.effect(async () => {
    const inUse = await isPortInUse(RESCUE_PORT);
    if (inUse) {
      console.log(`[rescue-bootloader] rescue server already running on port ${RESCUE_PORT}`);
      return () => {};
    }
    child = startRescueServer();
    return () => {
      // 不杀掉 detached 的 rescue-server，让它在 DSH 重启期间继续存活
      // 新 DSH 启动后会检测到端口已占用而不会重复启动
      child = null;
    };
  }, 'rescue-bootloader: launch rescue server');
}

export { apply, inject, name };
