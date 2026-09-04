import { _internals as I } from '../lib/index.js';
import { spawnSync } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

let fails = 0;
function ok(cond, msg) { if (!cond) { fails++; console.log('FAIL: ' + msg); } else console.log('PASS: ' + msg); }

const R = 'C:/x/dsh_rescue.py';
const PYEXE = 'C:/py/pythoncore-3.14/python.exe';
const py = { cmd: PYEXE, prefix: [] };
const CRLF = '\r\n';

// ===== 1. 静态文本：三形态严格判定 =====
const bc = I.blockCmd(py, R, CRLF);
ok(bc.includes('if "%~1"=="web" goto dshrescue'), '文本-批处理: dsh web 位置判定');
ok(bc.includes('if "%~1"=="--profile" if "%~2"=="web" goto dshrescue'), '文本-批处理: --profile web 位置判定');
ok(!bc.includes('if not "%~1"=="web" if not "%~2"=="web"'), '文本-批处理: 旧位无关宽匹配已移除');
const bp = I.blockPs(py, R, CRLF);
ok(bp.includes("$args[0] -eq 'web'") && bp.includes("$args[0] -eq '--profile'") && bp.includes("$args[1] -eq 'web'"), '文本-ps1: 位置判定两形态');
ok(!bp.includes("-contains 'web'"), '文本-ps1: 宽匹配 -contains 已移除');
const bs = I.blockSh({ cmd: '/usr/bin/python3', prefix: [] }, '/home/u/dsh_rescue.py', '\n');
ok(bs.includes('[ "$1" = "web" ]') && bs.includes('[ "$1" = "--profile" ]') && bs.includes('[ "$2" = "web" ]'), '文本-sh: 三形态判定文本');
ok(!bs.includes('] || [ "$2"'), '文本-sh: 位无关旧式已移除');

// ===== 2. 旧补丁夹具：narrow(v1.0) 与 wide(v1.1.2) 均被摘除并升级，幂等 =====
const wrapCmd = (condLines) => ['@ECHO off','GOTO start',':find_dp0','SET dp0=%~dp0','EXIT /b',':start','SETLOCAL','CALL :find_dp0','','IF EXIST "%dp0%/node.exe" (',')','', ...condLines, '', ':rundsh','endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%/node_modules/@deepseek-ai/dsh/lib/bin.js" %*',''].join(CRLF);
const narrow = wrapCmd(['REM ' + I.MARKER, 'if /I not "%~1"=="web" goto rundsh', 'if not EXIST "' + R + '" goto rundsh', 'endLocal', '"' + PYEXE + '" "' + R + '"', 'exit /b %ERRORLEVEL%']);
const wide = wrapCmd(['REM ' + I.MARKER, 'if not "%~1"=="web" if not "%~2"=="web" goto rundsh', 'if not EXIST "' + R + '" goto rundsh', 'endLocal', '"' + PYEXE + '" "' + R + '"', 'exit /b %ERRORLEVEL%']);
for (const [name, src] of [['v1.0', narrow], ['v1.1.2', wide]]) {
  const s = I.stripCmdBlock(src);
  ok(s && !s.includes('DSH Rescue') && s.includes(':rundsh') && s.includes('node_modules/@deepseek-ai/dsh'), '旧块清理(' + name + ')且骨架保留');
  const up = I.insertCmd(s, I.blockCmd(py, R, CRLF));
  ok(up.includes('goto dshrescue') && !up.includes('if not "%~2"=="web" goto rundsh'), '升级为严格块(' + name + ')');
  ok(I.stripCmdBlock(up) === s, '幂等 strip(insert(x))==x (' + name + ')');
}

// ===== 3. 真实行为：cmd.exe 跑生成的批处理块 =====
const dir = mkdtempSync(join(tmpdir(), 'dshr-'));
const cLines = I.blockCmd(py, R, CRLF).split(CRLF).map((l) => {
  if (l.startsWith('"') && l.includes(R)) return 'echo RESCUE';
  if (l.startsWith('if not EXIST')) return 'if not EXIST "%~f0" goto rundsh';
  return l;
});
const cFile = join(dir, 'dsh_rtest.cmd');
writeFileSync(cFile, ['@echo off', 'SETLOCAL', ...cLines, ':rundsh', 'echo NORMAL'].join(CRLF));
const runCmd = (args) => (spawnSync('cmd.exe', ['/d','/c','"'+cFile+'"'].concat(args), { encoding: 'utf8', windowsHide: true, windowsVerbatimArguments: true }).stdout || '');
ok(runCmd(['web','--no-open']).includes('RESCUE'), '实跑-批处理: dsh web -> 救援');
ok(runCmd(['--profile','web']).includes('RESCUE'), '实跑-批处理: dsh --profile web -> 救援');
const o3 = runCmd(['plugin','--profile','web','add']);
ok(o3.includes('NORMAL') && !o3.includes('RESCUE'), '实跑-批处理: dsh plugin --profile web -> 不触发');
const o4 = runCmd(['--version']);
ok(o4.includes('NORMAL') && !o4.includes('RESCUE'), '实跑-批处理: dsh --version -> 不触发');

// ===== 4. 真实行为：powershell 跑生成的 ps1 块 =====
const pLines = I.blockPs(py, R, CRLF).split(CRLF).map((l) => {
  if (l.trimStart().startsWith("& '")) return '    Write-Output RESCUE';
  if (l.includes('exit $LASTEXITCODE')) return '    exit 0';
  if (l.includes('$rescuePs =')) return '  $rescuePs = $PSCommandPath';
  return l;
});
const pFile = join(dir, 'dsh_rtest.ps1');
writeFileSync(pFile, pLines.concat(['Write-Output NORMAL']).join(CRLF));
const runPs = (args) => (spawnSync('powershell.exe', ['-NoProfile','-ExecutionPolicy','Bypass','-File',pFile].concat(args), { encoding: 'utf8', windowsHide: true }).stdout || '');
ok(runPs(['web']).includes('RESCUE'), '实跑-ps1: dsh web -> 救援');
ok(runPs(['--profile','web']).includes('RESCUE'), '实跑-ps1: dsh --profile web -> 救援');
const q3 = runPs(['plugin','--profile','web','add']);
ok(q3.includes('NORMAL') && !q3.includes('RESCUE'), '实跑-ps1: dsh plugin --profile web add -> 不触发（WebUI 误触发根因消除）');
const q4 = runPs(['--version']);
ok(q4.includes('NORMAL') && !q4.includes('RESCUE'), '实跑-ps1: dsh --version -> 不触发');

// ===== 5. 杂项回归：乱码历史块清理、py -3 前缀、discoverPython =====
const legacyGarbled = ['#!/usr/bin/env pwsh','$basedir=x','','# === DSH Rescue: \u62e6\u622a web \u5b50\u547d\u4ee4 ===','if ($args.Count -gt 0) {','  & dead','}','','$exe=""'].join(CRLF);
const s4 = I.stripMarkerBlock(legacyGarbled);
ok(!s4.includes('DSH Rescue') && s4.includes('$basedir=') && s4.includes('$exe=""'), '乱码历史 ps1 块被清理且骨架保留');
const q2 = I.blockPs({ cmd: 'C:/Windows/py.exe', prefix: ['-3'] }, R, '\n');
ok(q2.includes("-3' $rescuePs"), 'py -3 前缀嵌入 ps1 调用');
const c2 = I.blockCmd({ cmd: 'C:/Windows/py.exe', prefix: ['-3'] }, R, '\n');
ok(c2.includes('"C:/Windows/py.exe" -3 "' + R + '"'), 'py -3 前缀嵌入批处理调用');
const dp = I.discoverPython();
ok(dp && dp.cmd, 'discoverPython 可用: ' + (dp && dp.cmd));

console.log(fails === 0 ? 'ALL TESTS PASSED' : fails + ' TESTS FAILED');
process.exit(fails === 0 ? 0 : 1);
