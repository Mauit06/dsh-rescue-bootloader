import { _internals as I } from '../lib/index.js';
import { spawnSync } from 'node:child_process';
import { writeFileSync, readFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

let fails = 0;
function ok(cond, msg) { if (!cond) { fails++; console.log('FAIL: ' + msg); } else console.log('PASS: ' + msg); }

const CRLF = '\r\n';
const dir = mkdtempSync(join(tmpdir(), 'pair-'));
const R = 'C:/x/dsh_rescue.py';
const py = { cmd: 'C:/py/python.exe', prefix: [] };

const cmdBase = ['@ECHO off', 'GOTO start', ':find_dp0', 'SET dp0=%~dp0', 'EXIT /b', ':start', 'SETLOCAL', 'CALL :find_dp0', '', 'IF EXIST x (', ')', '', ':rundsh', 'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  "%dp0%/node_modules/@deepseek-ai/dsh/lib/bin.js" %*', ''].join(CRLF);
const psBase = ['#!/usr/bin/env pwsh', '$basedir=Split-Path $MyInvocation.MyCommand.Definition -Parent', '', '$exe=""', 'exit 0', ''].join(CRLF);

const cmdPatched = I.insertCmd(cmdBase, I.blockCmd(py, R, CRLF));
const psPatched = I.insertPs(psBase, I.blockPs(py, R, CRLF), CRLF);
ok(cmdPatched !== cmdBase && psPatched !== psBase, '插入产生了变化');

const inF = join(dir, 'io.json');
const outF = join(dir, 'oo.json');
writeFileSync(inF, JSON.stringify({ cmd: cmdPatched, ps1: psPatched }));

const pyExe = (() => { try { return readFileSync('C:/Users/Lenovo/.dsh/profiles/web/node_modules/dsh-rescue-bootloader/data/python.path', 'utf8').trim(); } catch { return 'python'; } })();
const repo = process.cwd().split('\\\\').join('/');
const code = [
"import json, sys",
"from pathlib import Path",
"sys.path.insert(0, r'" + process.cwd().replace(/\+/g, '\\') + "')",
"import uninstall as U",
"d = json.load(open(sys.argv[1], encoding='utf-8'))",
"c1, ch1 = U.strip_batch(d['cmd'])",
"c2, ch2 = U.strip_marker(d['ps1'])",
"json.dump({'cmd': c1, 'ps1': c2, 'c1': ch1, 'c2': ch2}, open(sys.argv[2], 'w', encoding='utf-8'))",
].join('\n');
const inFA = inF.replace(/\\/g, '/');
const outFA = outF.replace(/\\/g, '/');
const r = spawnSync(pyExe, ['-c', code, inFA, outFA], { encoding: 'utf8', windowsHide: true, cwd: process.cwd() });
if (r.status !== 0) { console.log('py stderr: ' + (r.stderr || r.stdout)); process.exit(2); }
const got = JSON.parse(readFileSync(outF, 'utf8'));
ok(got.cmd === cmdBase, 'Python strip_batch 字节级还原 JS 生成的批处理块');
ok(got.ps1 === psBase, 'Python strip_marker 字节级还原 JS 生成的 ps1 块');
ok(got.c1 === true && got.c2 === true, 'strip 报告 changed=true');
ok(got.cmd.includes(':rundsh') && got.cmd.includes('endLocal & goto #_undefined_#'), 'npm 语义行无损');

console.log(fails === 0 ? 'PAIR-ALL-PASSED' : fails + ' PAIR FAILURES');
process.exit(fails === 0 ? 0 : 1);
