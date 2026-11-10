import hmac
import os
import secrets
import socket
import subprocess
import threading
import time
from http.cookies import SimpleCookie, CookieError
from . import storage
def local_ipv4():
    addresses={"127.0.0.1"}
    try:
        import re
        output=subprocess.check_output(["/sbin/ifconfig"],text=True)
        addresses.update(re.findall(r"\binet (\d+\.\d+\.\d+\.\d+)",output))
    except (OSError,subprocess.SubprocessError):
        try: addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
        except OSError: pass
    return sorted(addresses)
class Access:
    def __init__(self,code=None):
        if code is None:
            path=storage.DATA/"access-code.txt"
            if not path.exists():
                fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,"w",encoding="utf-8") as f: f.write("-".join(secrets.token_hex(2) for _ in range(3))+"\n")
            path.chmod(0o600)
            code=path.read_text(encoding="utf-8").strip()
        self.code=code; self.sessions={}; self.attempts={}; self.lock=threading.Lock()
    def authenticated(self,handler):
        hostname=handler.headers.get("Host","").split(":")[0]
        if getattr(handler.server,"allow_local_access",True) and handler.client_address[0]=="127.0.0.1" and hostname in ["127.0.0.1","localhost"]: return True
        try:
            cookie=SimpleCookie(handler.headers.get("Cookie",""))
            token=cookie["radar_session"].value if "radar_session" in cookie else ""
        except CookieError: return False
        with self.lock:
            expiry=self.sessions.get(token,0)
            if expiry and expiry<time.time(): self.sessions.pop(token,None)
            return expiry>time.time()
    def login(self,code,ip):
        now=time.time()
        with self.lock:
            self.attempts={key:value for key,value in self.attempts.items() if now-value[0]<300}
            started,count=self.attempts.get(ip,(now,0))
            if count>=6: return 429,None
            if not isinstance(code,str) or not hmac.compare_digest(code.strip().lower().encode(),self.code.lower().encode()):
                self.attempts[ip]=(started,count+1); return 401,None
            self.attempts.pop(ip,None)
            self.sessions={key:value for key,value in self.sessions.items() if value>now}
            if len(self.sessions)>=100: self.sessions.pop(next(iter(self.sessions)))
            token=secrets.token_urlsafe(32); self.sessions[token]=now+7*86400
            return 200,token
