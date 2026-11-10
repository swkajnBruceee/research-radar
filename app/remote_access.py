"""An authenticated loopback-only gateway and an accountless HTTPS tunnel.

No collectors or reading workers are started here. The private LAN service and
this gateway share the canonical data directory, but never the local auth bypass.
"""
import argparse
import json
import os
import queue
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import unquote, urlparse
from . import connection, remote_status
from .access import Access
from .server import Handler, require

GATEWAY_HOST = 'remote.research-radar.invalid'


class RemoteHandler(Handler):
    def setup(self):
        self.request.settimeout(20)
        super().setup()

    def log_message(self, *_):
        # Never log request query strings, cookies, access codes or payloads.
        pass

    def mutation_allowed(self):
        require(self.valid_host(), '无效访问主机')
        origin = self.headers.get('Origin')
        require(not origin or origin == self.server.public_origin, '不允许跨站写入')

    def respond(self, status, payload, ctype='application/json; charset=utf-8', filename=None, headers=None):
        headers = dict(headers or {})
        if 'Set-Cookie' in headers:
            headers['Set-Cookie'] += '; Secure'
        headers['Strict-Transport-Security'] = 'max-age=86400'
        return super().respond(status, payload, ctype, filename, headers)

    def dispatch(self, method):
        if not self.server.public_origin:
            return self.respond(503, {'error': '公网入口正在连接，请稍后重试'})
        if unquote(urlparse(self.path).path) == '/api/pairing/access-code':
            return self.respond(403, {'error': '请在 Mac 本机的配对页查看访问码'})
        return super().dispatch(method)


class Gateway(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=8768, access=None):
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(('127.0.0.1', port), RemoteHandler)
        self.allowed_hosts = [GATEWAY_HOST]
        self.pairing_port = 8765
        self.allow_local_access = False
        self.public_origin = ''
        self.access = access if access is not None else Access()

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def probe(url):
    try:
        request = urllib.request.Request(url + '/api/discovery', headers={'User-Agent': 'ResearchRadar-health/1'})
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status == 200 and json.loads(response.read(4096)).get('id') == connection.identity()
    except (OSError, ValueError):
        return False


def run(binary=None, port=8768):
    import re
    binary = binary or shutil.which('cloudflared')
    if not binary:
        raise RuntimeError('未安装 cloudflared；请先运行 brew install cloudflared')
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    gateway = Gateway(port)
    thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    thread.start()
    process = None
    remote_status.write('starting', message='正在建立 HTTPS 通道…')
    try:
        # The Host header is a fixed internal name, never localhost. Keep metrics
        # private too. No debug logging, auto-updates, or Cloudflare credentials.
        process = subprocess.Popen([binary, 'tunnel', '--no-autoupdate', '--url',
            'http://127.0.0.1:' + str(gateway.server_port), '--http-host-header', GATEWAY_HOST,
            '--metrics', '127.0.0.1:0', '--protocol', 'http2', '--edge-ip-version', '4',
            '--grace-period', '3s'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True)
        events = queue.Queue(maxsize=500)

        def consume():
            for line in process.stderr:
                try:
                    events.put_nowait(line)
                except queue.Full:
                    pass

        threading.Thread(target=consume, daemon=True).start()
        started = time.monotonic()
        url = ''
        registered = False
        last_probe = 0
        last_status = 0
        available = False
        failures = 0
        ever_available = False
        while not stop.wait(.25):
            if process.poll() is not None:
                raise RuntimeError('通道进程已退出，请检查 Mac 网络后重新启动。')
            while True:
                try:
                    line = events.get_nowait()
                except queue.Empty:
                    break
                match = re.search(remote_status.URL_PATTERN, line)
                if match and not url:
                    url = match.group(0)
                    gateway.public_origin = url
                    print('HTTPS 入口：' + url + '/', flush=True)
                if 'Registered tunnel connection' in line:
                    registered = True
            now = time.monotonic()
            if url and registered and now - last_probe >= (30 if available else 5):
                available = probe(url)
                ever_available = ever_available or available
                failures = 0 if available else failures + 1
                last_probe = time.monotonic()
                if failures >= 6:
                    raise RuntimeError('公网连通检查连续失败，通道将重新建立。')
            if not ever_available and now - started > 150:
                raise RuntimeError('公网通道连接超时；当前网络可能限制 Cloudflare Tunnel 的连接端口。')
            if now - last_status > 10:
                remote_status.write('available' if available else 'connecting', url if available else '',
                    '可跨网络访问；Mac 需保持在线，通道重建后地址会变化。' if available else '正在验证公网连通性…')
                last_status = now
        return 0
    except Exception as exc:
        remote_status.write('error', message=str(exc))
        print(str(exc), flush=True)
        return 1
    finally:
        gateway.public_origin = ''
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process and process.stderr:
            process.stderr.close()
        gateway.shutdown()
        gateway.server_close()
        if stop.is_set():
            remote_status.write('offline', message='公网通道已停止；本机与校园网访问仍可使用。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cloudflared')
    parser.add_argument('--port', type=int, default=8768)
    args = parser.parse_args()
    return run(args.cloudflared, args.port)


if __name__ == '__main__':
    raise SystemExit(main())
