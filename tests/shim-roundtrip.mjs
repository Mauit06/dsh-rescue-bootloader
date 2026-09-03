
import { _internals as I } from '../lib/index.js';

let fails = 0;
function ok(cond, msg) { if (!cond) { fails++; console.log('FAIL: ' + msg); } else console.log('PASS: ' + msg); }

const R = 'C:/x/dsh_rescue.py';
const PYEXE = 'C:/py/pythoncore-3.14/python.exe';
const py = { cmd: PYEXE, prefix: [] };

// 旧批处理补丁（窄条件 + 无 end 标记），含真实 npm 结构
const oldCmd = [
  '@ECHO off', 'GOTO start', ':find_dp0', 'SET dp0=%~dp0', 'EXIT /b', ':start', 'SETLOCAL', 'CALL :find_dp0', '',
  'IF EXIST "%dp0%/node.exe" (', '  SET "_prog=%dp0%/node.exe"', ') ELSE (', '  SET "_prog=node"', ')', '',
  'REM === DSH Rescue: intercept web subcommand ===',
  'if /I not "%~1"=="web" goto rundsh',
  'if not EXIST "' + R + '" goto rundsh',
  'endLocal',
  '"' + PYEXE + '" "' + R + '"',
  'exit /b %ERRORLEVEL%',
  '',
  ':rundsh',
  'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%/node_modules/@deepseek-ai/dsh/lib/bin.js" %*',
  ''
].join('\r\n');

const oldPs1 = [
  '#!/usr/bin/env pwsh',
  '$basedir=Split-Path $MyInvocation.MyCommand.Definition -Parent',
  '',
  '# === DSH Rescue: intercept web subcommand ===',
  'if ($args.Count -gt 0 -and $args[0] -eq \'web\') {',
  '  $rescuePs = \'' + R + '\'',
  '  if (Test-Path $rescuePs) {',
  '    & \'' + PYEXE + '\' $rescuePs',
  '    exit $LASTEXITCODE',
  '  }',
  '}',
  '',
  '$exe=""',
  'exit 0',
  ''
].join('\r\n');

const cleanSh = '#!/bin/sh\nbasedir=$(dirname "$0")\nexec node "$basedir/node_modules/@deepseek-ai/dsh/lib/bin.js" "$@"\n';

// ---- strip 旧格式 ----
const s1 = I.stripCmdBlock(oldCmd);
ok(s1 && !s1.includes('DSH Rescue'), '旧批处理补丁被剥离');
ok(s1 && s1.includes(':rundsh') && s1.includes('GOTO start'), '批处理骨架完整保留');

const s2 = I.stripMarkerBlock(oldPs1);
ok(s2 && !s2.includes('DSH Rescue'), '旧 ps1 补丁被剥离');
ok(s2 && s2.includes('$basedir=') && s2.includes('$exe=""'), 'ps1 骨架完整保留');

// ---- 新块插入 + 结构校验 ----
const p1 = I.insertCmd(s1, I.blockCmd(py, R, '\r\n'));
ok(p1.includes('if not "%~1"=="web" if not "%~2"=="web" goto rundsh'), '批处理新条件覆盖 --profile web');
ok(p1.split('=== DSH Rescue').length - 1 === 1, '批处理拦截块唯一');
ok(p1.includes(':rundsh') && p1.includes('node_modules/@deepseek-ai/dsh'), '关键行未丢失');
const p1b = I.insertCmd(I.stripCmdBlock(p1), I.blockCmd(py, R, '\r\n'));
ok(p1b === p1, '批处理幂等');
ok(I.stripCmdBlock(p1) === s1, '批处理 strip(insert(x)) == x');

const q1 = I.insertPs(s2, I.blockPs(py, R, '\r\n'), '\r\n');
ok(q1.includes("$args -contains 'web'"), 'ps1 新条件覆盖 --profile web');
ok(q1.includes(I.END) && q1.split('=== DSH Rescue').length - 1 === 2, 'ps1 含 end 标记且块唯一');
const q1b = I.insertPs(I.stripMarkerBlock(q1), I.blockPs(py, R, '\r\n'), '\r\n');
ok(q1b === q1, 'ps1 幂等');
ok(I.stripMarkerBlock(q1) === s2, 'ps1 strip(insert(x)) == x');

const shBlock = I.blockSh({ cmd: '/usr/bin/python3', prefix: [] }, '/home/u/dsh_rescue.py', '\n');
const r1 = I.insertSh(cleanSh, shBlock);
ok(r1.split('\n')[0] === '#!/bin/sh' && r1.split('\n')[1].includes(I.MARKER), 'sh 块插在 shebang 之后');
ok(I.stripMarkerBlock(r1) === cleanSh, 'sh 卸载完全还原');
ok(I.insertSh(I.stripMarkerBlock(r1), shBlock) === r1, 'sh 幂等');

// ---- py -3 前缀 ----
const q2 = I.blockPs({ cmd: 'C:/Windows/py.exe', prefix: ['-3'] }, R, '\n');
ok(q2.includes("-3' $rescuePs"), 'py -3 前缀嵌入 ps1 调用');
const c2 = I.blockCmd({ cmd: 'C:/Windows/py.exe', prefix: ['-3'] }, R, '\n');
ok(c2.includes('"C:/Windows/py.exe" -3 "' + R + '"'), 'py -3 前缀嵌入批处理调用');

// ---- 真机 discoverPython ----
const dp = I.discoverPython();
ok(dp && dp.cmd, 'discoverPython 可用: ' + (dp && dp.cmd) + ' prefix=' + JSON.stringify(dp && dp.prefix));

// 历史乱码中文块也应被前缀匹配清理
const legacyGarbled = ['#!/usr/bin/env pwsh','$basedir=x','','# === DSH Rescue: \u62e6\u622a web \u5b50\u547d\u4ee4 ===','if ($args.Count -gt 0) {','  & dead','}','','$exe=""'].join('\r\n');
const s4 = I.stripMarkerBlock(legacyGarbled);
ok(!s4.includes('DSH Rescue') && s4.includes('$basedir=') && s4.includes('$exe=""'), '乱码历史 ps1 块被清理且骨架保留');

console.log(fails === 0 ? 'ALL TESTS PASSED' : fails + ' TESTS FAILED');
process.exit(fails === 0 ? 0 : 1);