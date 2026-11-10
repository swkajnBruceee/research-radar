#!/usr/bin/env python3
"""Manage the user's separate HTTPS gateway without restarting reading workers."""
import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import remote_status, storage

LABEL = 'com.bruce.research-radar-remote'
DOMAIN = 'gui/' + str(os.getuid())
PLIST = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'remove', 'status'])
    args = parser.parse_args()
    if args.action == 'status':
        print(remote_status.read())
        return subprocess.call(['launchctl', 'print', DOMAIN + '/' + LABEL])
    subprocess.run(['launchctl', 'bootout', DOMAIN + '/' + LABEL],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if subprocess.run(['launchctl', 'print', DOMAIN + '/' + LABEL],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            break
        time.sleep(.2)
    else:
        raise RuntimeError('旧公网通道尚未退出，请稍后再试。')
    if args.action == 'remove':
        PLIST.unlink(missing_ok=True)
        remote_status.write('offline', message='公网通道已停用；本机与校园网服务保持运行。')
        print('已停用公网通道，研究数据保留。')
        return 0
    binary = shutil.which('cloudflared')
    if not binary:
        raise RuntimeError('请先安装 cloudflared：brew install cloudflared')
    runtime = Path.home() / 'Library/Application Support/ResearchRadar/Runtime'
    if not (runtime / 'run.py').is_file():
        raise RuntimeError('请先执行 python3 scripts/manage_service.py install 安装本机服务。')
    # Safe to copy sources: no Python process is restarted, no private data copied.
    for folder in ['app', 'public']:
        shutil.copytree(ROOT / folder, runtime / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    logs = storage.DATA / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    value = {'Label': LABEL, 'ProgramArguments': [sys.executable, '-m', 'app.remote_access',
                '--cloudflared', binary], 'WorkingDirectory': str(runtime),
             'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 60,
             'EnvironmentVariables': {'PYTHONUNBUFFERED': '1', 'RADAR_DATA_DIR': str(storage.DATA.resolve())},
             'StandardOutPath': str(logs.resolve() / 'remote-access.log'),
             'StandardErrorPath': str(logs.resolve() / 'remote-access-error.log')}
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(value))
    PLIST.chmod(0o600)
    subprocess.run(['launchctl', 'bootstrap', DOMAIN, str(PLIST)], check=True)
    print('已启用登录后常驻的 HTTPS 通道；临时地址请在本机 /pair 页面查看。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
