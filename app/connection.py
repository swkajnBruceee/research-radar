"""Stable local identity, pairing links, and Bonjour advertisement."""
import atexit
import json
import socket
import subprocess
import threading
import urllib.parse
import uuid
from pathlib import Path
from . import storage

_process=None

def identity():
    path=storage.DATA/'instance-id.txt'
    storage.DATA.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        try:
            with path.open('x') as f:f.write(str(uuid.uuid4()))
        except FileExistsError:pass
    return path.read_text().strip()

def local_hostname():
    try:
        host=subprocess.check_output(['/usr/sbin/scutil','--get','LocalHostName'],text=True,timeout=3).strip()
    except (OSError,subprocess.SubprocessError):host=socket.gethostname().split('.')[0]
    return host+'.local'

def pairing(port=8765):
    from .access import local_ipv4
    from .remote_status import read
    ips=[x for x in local_ipv4() if x!='127.0.0.1' and not x.startswith('198.18.')]
    address='http://'+local_hostname()+':'+str(port)+'/'
    return {'id':identity(),'name':'具身研究台','address':address,'alternatives':['http://'+ip+':'+str(port)+'/' for ip in ips],
            'invitation':'embodiedradar://connect?'+urllib.parse.urlencode({'url':address,'id':identity()}),
            'remote':read(),
            'service_type':'_embodiedradar._tcp.','note':'配对链接不包含访问码；同网设备仍需允许互通。'}

def advertise(port):
    global _process
    try:
        _process=subprocess.Popen(['/usr/bin/dns-sd','-R','具身研究台','_embodiedradar._tcp','local',str(port),'id='+identity(),'path=/'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        atexit.register(stop)
    except OSError:pass

def stop():
    if _process and _process.poll() is None:_process.terminate()
