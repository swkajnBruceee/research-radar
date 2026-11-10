import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from app import storage, remote_status
from app.access import Access
from app.remote_access import Gateway, GATEWAY_HOST


class RemoteAccessTests(unittest.TestCase):
    def test_incremental_reading_and_receipt_require_auth_and_a_matching_content_version(self):
        document='b'*64;version='a'*64;device='01234567-89ab-cdef-0123-456789abcdef'
        payload={'version':version,'manifest':{'version':version,'count':1,'documents':{'paper':document},'reading_versions':{'paper':'c'*64}},'readings':{'paper':{'document':{'id':document}}}}
        self.assertEqual(self.request('/api/content/reading?item_id=paper&version='+version)[0],401)
        _,_,headers=self.request('/api/login','POST',{'code':'test-1234-abcd'},Origin=self.server.public_origin)
        cookie=headers['Set-Cookie'].split(';',1)[0]
        with patch('app.public_content.package',return_value=payload):
            self.assertEqual(self.request('/api/content/reading?item_id=paper&version=old',Cookie=cookie)[0],412)
            status,raw,_=self.request('/api/content/reading?item_id=paper&version='+version,Cookie=cookie)
            self.assertEqual(status,200);self.assertEqual(json.loads(raw)['reading_version'],'c'*64)
            receipt=dict(device_id=device,version=version,documents={'paper':document})
            self.assertEqual(self.request('/api/content/receipt','POST',receipt,Cookie=cookie,Origin='https://evil.example')[0],400)
            status,raw,_=self.request('/api/content/receipt','POST',receipt,Cookie=cookie,Origin=self.server.public_origin)
            self.assertEqual(status,200);self.assertTrue(json.loads(raw)['current'])
            status,raw,_=self.request('/api/content/delivery?device='+device,Cookie=cookie)
            self.assertTrue(json.loads(raw)['current'])
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = storage.DATA, storage.DB
        storage.DATA = Path(self.temp.name)
        storage.DB = storage.DATA / 'test.sqlite3'
        self.server = Gateway(0, Access('test-1234-abcd'))
        self.server.public_origin = 'https://test-example.trycloudflare.com'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        storage.DATA, storage.DB = self.old
        self.temp.cleanup()

    def request(self, path, method='GET', body=None, **headers):
        headers = {'Host': GATEWAY_HOST, 'Content-Type': 'application/json', **headers}
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request(method, path, json.dumps(body) if body else None, headers)
        response = conn.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        conn.close()
        return result

    def test_all_private_routes_are_gated_despite_loopback_and_forwarded_headers(self):
        for path in ['/api/state', '/api/content', '/api/export', '/api/pairing',
                     '/api/reading-queue', '/api/integrations/status','/api/content/receipt','/api/content/delivery']:
            self.assertEqual(self.request(path, **{'X-Forwarded-Host': 'localhost',
                'X-Forwarded-Proto': 'http'})[0], 401)
        self.assertEqual(self.request('/api/state', Host='localhost')[0], 400)
        self.assertEqual(self.request('/api/state', Host='127.0.0.1')[0], 400)
        status, raw, _ = self.request('/api/discovery')
        self.assertEqual(status, 200)
        self.assertEqual(set(json.loads(raw)), {'id', 'name', 'protocol'})
        self.assertNotIn(b'test-1234-abcd', self.request('/')[1])

    def test_secure_login_exact_https_origin_and_authenticated_access(self):
        for origin in ['https://evil.example', 'http://' + GATEWAY_HOST,
                       self.server.public_origin + '.evil.example', 'null']:
            self.assertEqual(self.request('/api/login', 'POST', {'code': 'test-1234-abcd'}, Origin=origin)[0], 400)
        status, _, headers = self.request('/api/login', 'POST', {'code': 'test-1234-abcd'}, Origin=self.server.public_origin)
        self.assertEqual(status, 200)
        for attribute in ['Secure', 'HttpOnly', 'SameSite=Strict']:
            self.assertIn(attribute, headers['Set-Cookie'])
        cookie = headers['Set-Cookie'].split(';', 1)[0]
        self.assertEqual(self.request('/api/health', Cookie=cookie)[0], 200)
        self.assertEqual(self.request('/api/pairing/access-code', Cookie=cookie)[0], 403)
        self.assertEqual(self.request('/api/pairing%2Faccess-code', Cookie=cookie)[0], 403)
        # Native clients intentionally have no Origin header.
        self.assertEqual(self.request('/api/login', 'POST', {'code': 'test-1234-abcd'})[0], 200)

    def test_no_public_origin_fails_closed(self):
        self.server.public_origin = ''
        self.assertEqual(self.request('/api/login', 'POST', {'code': 'test-1234-abcd'})[0], 503)
        self.assertEqual(self.request('/api/discovery')[0], 503)

    def test_status_hides_stale_or_invalid_addresses(self):
        remote_status.write('available', 'https://test-example.trycloudflare.com')
        self.assertEqual(remote_status.read()['state'], 'available')
        with patch('app.remote_status.time.time', return_value=time.time() + 100):
            self.assertEqual(remote_status.read()['url'], '')
        remote_status.write('available', 'http://localhost:8765/?token=secret')
        self.assertEqual(remote_status.read()['url'], '')
        self.assertEqual((storage.DATA / 'remote-access.json').stat().st_mode & 0o777, 0o600)
