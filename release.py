#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键发布：打包 -> 推送 -> 创建 GitHub Release -> 上传 .tgz（替代 release.ps1）。"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = 'Mauit06/dsh-rescue-bootloader'
API = 'https://api.github.com'
UPLOAD = 'https://uploads.github.com'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] [release] {msg}', flush=True)


def read_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def api(method, url, token, data=None, headers=None, raw=None):
    req = urllib.request.Request(url, method=method)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('User-Agent', 'dsh-agent')
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
    elif raw is not None:
        body = raw
    try:
        with urllib.request.urlopen(req, body) as resp:
            content = resp.read().decode('utf-8')
            try:
                return resp.status, json.loads(content)
            except Exception:
                return resp.status, content
    except urllib.error.HTTPError as e:
        content = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f"HTTP {e.code}: {content}")


def main():
    p = argparse.ArgumentParser(description='DSH 救砖发布工具 (Python)')
    p.add_argument('--token', default=os.environ.get('GH_TOKEN'), help='repo 权限 token')
    p.add_argument('--repo', default=REPO)
    p.add_argument('--version', default=None)
    p.add_argument('--note-file', default='RELEASE_BODY.md')
    p.add_argument('--skip-push', action='store_true')
    p.add_argument('--skip-pack', action='store_true')
    args = p.parse_args()

    if not args.token:
        print('ERROR: 需要 repo 权限的 token (GH_TOKEN 或 --token)')
        sys.exit(1)

    ver = args.version
    if not ver:
        ver = read_json('package.json').get('version')
    if not ver:
        print('ERROR: 无版本号'); sys.exit(1)
    tag = f'v{ver}'
    tgz = f'dsh-rescue-bootloader-{ver}.tgz'
    repo = args.repo

    # 1) 打包
    if not Path(tgz).exists():
        if args.skip_pack:
            print(f'ERROR: {tgz} 不存在且 --skip-pack'); sys.exit(1)
        log(f'npm pack -> {tgz}')
        subprocess.run(['npm', 'pack'], check=True)
    else:
        log(f'复用已有 {tgz}')

    # 2) 推送
    if not args.skip_push:
        log('推送 main + tags ...')
        subprocess.run(['git', 'push', '-f', f'https://{args.token}@github.com/{repo}.git', 'main', '--tags'], check=True)
        log('推送完成')
    else:
        log('跳过推送')

    # 3) 建 Release
    log(f'创建 Release {tag} ...')
    note = ''
    if Path(args.note_file).exists():
        note = Path(args.note_file).read_text(encoding='utf-8')
    payload = dict(tag_name=tag, target_commitish='main', name=f'dsh-rescue-bootloader {tag}', body=note, draft=False, prerelease=False)
    status, rel = api('POST', f'{API}/repos/{repo}/releases', args.token, data=payload)
    if status not in (200, 201):
        print(f'ERROR: 建 Release 失败 {status}: {rel}'); sys.exit(1)
    log(f'Release 已创建: {rel.get("html_url")} (id={rel.get("id")})')

    # 4) 上传附件
    log(f'上传 {tgz} ...')
    raw = Path(tgz).read_bytes()
    up_url = f'{UPLOAD}/repos/{repo}/releases/{rel["id"]}/assets?name={tgz}'
    status, asset = api('POST', up_url, args.token, raw=raw, headers={'Content-Type': 'application/octet-stream'})
    if status not in (200, 201):
        print(f'ERROR: 上传附件失败 {status}: {asset}'); sys.exit(1)
    log(f'附件已上传: {asset.get("name")}')

    print()
    print(f'DONE. Release URL: {rel.get("html_url")}')


if __name__ == '__main__':
    main()