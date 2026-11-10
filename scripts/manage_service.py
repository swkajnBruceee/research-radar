#!/usr/bin/env python3
"""Install/remove the per-user Mac agent. No root or system power changes."""
import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app import storage
LABEL='com.bruce.embodied-research-radar'
PLIST=Path.home()/'Library/LaunchAgents'/ (LABEL+'.plist')
DOMAIN='gui/'+str(os.getuid())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['install','remove','status']);args=parser.parse_args()
    if args.action=='status':
        return subprocess.call(['launchctl','print',DOMAIN+'/'+LABEL])
    subprocess.run(['launchctl','bootout',DOMAIN+'/'+LABEL],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    # bootout can return before a graceful HTTP shutdown has fully removed the job.
    for _ in range(40):
        loaded=subprocess.run(['launchctl','print',DOMAIN+'/'+LABEL],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if loaded.returncode:break
        time.sleep(.2)
    else:raise RuntimeError('旧服务仍在退出，请稍后重新执行；数据已保留')
    if args.action=='remove':
        PLIST.unlink(missing_ok=True);print('已停用登录常驻；研究数据保留。');return 0
    # launchd cannot access Desktop on current macOS without extra privacy grants.
    # Keep a deployable runtime copy and one canonical, linked data directory.
    home=Path.home()/'Library/Application Support/ResearchRadar'
    runtime=home/'Runtime';runtime.mkdir(parents=True,exist_ok=True)
    default_data=ROOT/'data'
    if storage.DATA==default_data and not default_data.is_symlink():
        destination=home/'Data'
        if destination.exists():raise RuntimeError('目标数据目录已存在，请先核对，未覆盖任何数据')
        if default_data.exists():shutil.move(str(default_data),str(destination))
        else:destination.mkdir()
        default_data.symlink_to(destination,target_is_directory=True)
    canonical_data=storage.DATA.resolve()
    for folder in ['app','public','tools','content']:
        shutil.copytree(ROOT/folder,runtime/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(ROOT/'run.py',runtime/'run.py')
    logs=storage.DATA/'logs';logs.mkdir(parents=True,exist_ok=True)
    PLIST.parent.mkdir(parents=True,exist_ok=True)
    value={'Label':LABEL,'ProgramArguments':[sys.executable,str(runtime/'run.py'),'--lan'],
           'WorkingDirectory':str(runtime),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':15,
           'EnvironmentVariables':{'PYTHONUNBUFFERED':'1','RADAR_DATA_DIR':str(canonical_data)},
           'StandardOutPath':str(logs.resolve()/'service.log'),'StandardErrorPath':str(logs.resolve()/'service-error.log')}
    PLIST.write_bytes(plistlib.dumps(value));PLIST.chmod(0o600)
    for attempt in range(3):
        result=subprocess.run(['launchctl','bootstrap',DOMAIN,str(PLIST)],stderr=subprocess.PIPE,text=True)
        if not result.returncode:break
        if attempt==2:raise RuntimeError('用户服务未能启动：'+result.stderr.strip())
        time.sleep(1)
    print('已安装用户登录常驻服务。Mac 睡眠期间采集暂停；当前登录会话启动并在退出异常时重启。')
    return 0
if __name__=='__main__':sys.exit(main())
