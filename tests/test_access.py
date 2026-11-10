import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from app import storage
from app.access import Access
from app.server import Handler
class AccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.old=(storage.DATA,storage.DB)
        storage.DATA=Path(cls.temp.name);storage.DB=storage.DATA/"test.sqlite3"
        storage.init()
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.server.access=Access("test-1234-abcd")
        cls.server.allow_local_access=False
        cls.server.allowed_hosts=["127.0.0.1:"+str(cls.server.server_port),"10.1.2.3:"+str(cls.server.server_port)]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
        storage.DATA,storage.DB=cls.old;cls.temp.cleanup()
    def request(self,path,method="GET",body=None,cookie="",origin=None,host=None):
        headers={"Host":host or "10.1.2.3:"+str(self.server.server_port),"Content-Type":"application/json"}
        if cookie:headers["Cookie"]=cookie
        if origin:headers["Origin"]=origin
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port)
        conn.request(method,path,body=json.dumps(body) if body else None,headers=headers)
        res=conn.getresponse();result=(res.status,res.read(),dict(res.getheaders()));conn.close()
        return result
    def test_private_data_requires_login(self):
        self.assertEqual(self.request("/api/state")[0],401)
        self.assertEqual(self.request("/api/export")[0],401)
        self.assertEqual(self.request("/api/pairing")[0],401)
        self.assertEqual(self.request("/api/reading/arxiv:2303.04137")[0],401)
        self.assertEqual(self.request("/api/content")[0],401)
        self.assertEqual(self.request("/api/content/manifest")[0],401)
        status,raw,_=self.request("/api/discovery")
        self.assertEqual(status,200);self.assertEqual(set(json.loads(raw)),{'id','name','protocol'})
        self.assertNotIn(b'test-1234-abcd',raw)
        self.assertEqual(self.request("/api/integrations/export?target=notion&scope=all")[0],401)
        self.assertIn(b"access-code",self.request("/")[1])
        self.assertEqual(self.request("/login.js")[0],200)
    def test_login_read_and_write_from_lan_host(self):
        status,_,headers=self.request("/api/login","POST",{"code":"test-1234-abcd"})
        self.assertEqual(status,200)
        self.assertIn("HttpOnly",headers["Set-Cookie"])
        cookie=headers["Set-Cookie"].split(";",1)[0]
        self.assertEqual(self.request("/api/state",cookie=cookie)[0],200)
        status,raw,_=self.request("/api/items/arxiv:2303.04137","PATCH",{"notes":"LAN note"},cookie,"http://10.1.2.3:"+str(self.server.server_port))
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)["notes"],"LAN note")
        self.server.access.sessions[cookie.split("=",1)[1]]=time.time()-1
        self.assertEqual(self.request("/api/state",cookie=cookie)[0],401)
    def test_unknown_hosts_and_cross_origin_are_rejected(self):
        self.assertEqual(self.request("/api/login","POST",{"code":"test-1234-abcd"},origin="https://example.com")[0],400)
        self.assertEqual(self.request("/api/state",host="untrusted.example")[0],400)
    def test_reading_and_access_code_respect_authentication_boundaries(self):
        status,_,headers=self.request("/api/login","POST",{"code":"test-1234-abcd"})
        cookie=headers["Set-Cookie"].split(";",1)[0]
        status,raw,_=self.request("/api/reading/arxiv:2303.04137",cookie=cookie)
        self.assertEqual(status,200);self.assertIsNone(json.loads(raw)["analysis"])
        self.assertEqual(self.request("/api/reading/arxiv:2303.04137","POST",{"model":"invalid"},cookie)[0],400)
        self.assertEqual(self.request("/api/reading/no-paper",cookie=cookie)[0],404)
        self.assertEqual(self.request("/api/pairing/access-code",cookie=cookie)[0],403)
        status,raw,_=self.request("/api/pairing/access-code",cookie=cookie,host="127.0.0.1:"+str(self.server.server_port))
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)["code"],"test-1234-abcd")
    def test_wrong_codes_and_rate_limit(self):
        auth=Access("test-1234-abcd")
        for _ in range(6):self.assertEqual(auth.login("wrong","fixture-ip")[0],401)
        self.assertEqual(auth.login("test-1234-abcd","fixture-ip")[0],429)
        self.assertEqual(auth.login("test-1234-abcd","another-ip")[0],200)
        self.assertEqual(auth.login(None,"third-ip")[0],401)
