import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from app import storage, collectors
from app.server import Handler

ATOM=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2611.01234v2</id><title>Robot World Models</title><summary>Video prediction for robot manipulation.</summary><published>2026-11-01T00:00:00Z</published><updated>2026-11-03T00:00:00Z</updated><author><name>Alice</name></author></entry></feed>'''
RSS=b'''<rss><channel><item><title>Diffusion policy (arXiv:2611.01234v3 [cs.RO])</title><link>https://arxiv.org/abs/2611.01234</link><description>Imitation learning</description><pubDate>Tue, 03 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>'''

class RadarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="research-radar-test-")
        cls.old_data=storage.DATA; cls.old_db=storage.DB
        storage.DATA=Path(cls.temp.name); storage.DB=storage.DATA/"test.sqlite3"
        storage.init()
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.base="http://127.0.0.1:"+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()
        storage.DATA=cls.old_data; storage.DB=cls.old_db; cls.temp.cleanup()
    def request(self,path,method="GET",body=None,headers=None):
        data=json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(self.base+path,data=data,method=method,headers={"Content-Type":"application/json",**(headers or {})})
        try:
            with urllib.request.urlopen(req) as r:
                raw=r.read(); return r.status,json.loads(raw) if "application/json" in r.headers["Content-Type"] else raw
        except urllib.error.HTTPError as e:
            raw=e.read()
            return e.code,json.loads(raw) if "application/json" in e.headers.get("Content-Type","") else raw
    def test_seed_idempotent_and_historical(self):
        count=len(storage.all_items()); storage.init()
        self.assertEqual(len(storage.all_items()),count)
        self.assertTrue(all(x["curated"] for x in storage.all_items() if x["source_id"]=="foundation"))
    def test_reading_queue_http_actions_use_revisions_and_survive_backup(self):
        iid='arxiv:2611.88888'
        storage.upsert({'id':iid,'title':'Queue API example','url':'https://arxiv.org/abs/2611.88888v1','kind':'paper','source_id':'arxiv','published':'2026-11-03','updated':'2026-11-03','topics':['vla']})
        status,result=self.request('/api/reading-queue','POST',{'item_id':iid})
        self.assertEqual(status,202);tid=result['task_id']
        status,again=self.request('/api/reading-queue','POST',{'item_id':iid});self.assertEqual(again['task_id'],tid)
        row=next(t for t in result['queue']['tasks'] if t['id']==tid)
        status,changed=self.request('/api/reading-queue/'+tid,'POST',{'action':'cancel','revision':row['revision']})
        self.assertEqual(status,200);self.assertEqual(next(t for t in changed['queue']['tasks'] if t['id']==tid)['status'],'cancelled')
        status,_=self.request('/api/reading-queue/'+tid,'POST',{'action':'retry','revision':row['revision']});self.assertEqual(status,409)
        status,_=self.request('/api/reading-queue/'+tid,'POST',{'action':'retry','revision':True});self.assertEqual(status,400)
        status,state=self.request('/api/reading-queue');self.assertEqual(status,200);self.assertNotIn('lease_token',json.dumps(state))
        status,raw=self.request('/api/export');self.assertEqual(status,200)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            backup=json.loads(z.read('reading-queue.json'));self.assertTrue(any(t['id']==tid for t in backup['tasks']))
            self.assertNotIn('lease_token',json.dumps(backup))
    def test_atom_and_rss_deduplicate_versions(self):
        a=collectors.parse_feed(ATOM)[0]; r=collectors.parse_feed(RSS)[0]
        self.assertEqual(a["id"],r["id"]); self.assertEqual(a["authors"],"Alice")
        self.assertIn("world",a["topics"]); self.assertEqual(r["published"],"2026-11-03")
        self.assertEqual(collectors.parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"/>'),[])
        with self.assertRaises(Exception): collectors.parse_feed(b"<html/>")
    def test_update_preserves_user_work(self):
        item=collectors.parse_feed(ATOM)[0]; storage.upsert(item)
        status,_=self.request("/api/items/"+item["id"],"PATCH",{"notes":"A falsifiable hypothesis.","saved":True,"reading":"reading"})
        self.assertEqual(status,200)
        updated={**item,"summary":"Upstream revised summary.","updated":"2026-11-04"}
        self.assertEqual(storage.upsert(updated),"updated")
        actual=storage.get_item(item["id"])
        self.assertEqual(actual["notes"],"A falsifiable hypothesis.")
        self.assertTrue(actual["saved"]); self.assertEqual(actual["reading"],"reading")
        self.assertEqual(actual["summary"],updated["summary"])
        self.assertGreaterEqual(len(actual["events"]),2)
        self.assertTrue(any((storage.DATA/"notes").glob("*.md")))
    def test_curated_code_and_summary_survive_refresh(self):
        original=storage.get_item("arxiv:2406.09246")
        item={k:original[k] for k in storage.FIELDS if k not in ["analysis","curated","title_zh"]}
        item.update(summary="upstream",code_url="",updated="2026-11-04")
        storage.upsert({**item,"id":original["id"]})
        actual=storage.get_item(original["id"])
        self.assertEqual(actual["summary"],original["summary"])
        self.assertEqual(actual["code_url"],original["code_url"])
    def test_idea_crud_and_markdown(self):
        status,idea=self.request("/api/ideas","POST",{"title":"Can fewer steps work?","topic":"vla","hypothesis":"Equal success at lower latency.","experiment":"Hold data fixed."})
        self.assertEqual(status,201); self.assertEqual(idea["status"],"待调研")
        self.assertTrue((storage.DATA/"ideas"/(idea["id"]+".md")).exists())
        status,updated=self.request("/api/ideas/"+idea["id"],"PATCH",{"status":"实验中"})
        self.assertEqual(status,200); self.assertEqual(updated["status"],"实验中")
        self.assertEqual(updated["hypothesis"],idea["hypothesis"])
        self.assertEqual(self.request("/api/ideas/"+idea["id"],"DELETE")[0],200)
        self.assertFalse((storage.DATA/"ideas"/(idea["id"]+".md")).exists())
    def test_validation_and_cross_origin(self):
        for payload in [{"title":""},{"title":"x","topic":[]},{"title":"x","status":"invented"},{"title":"x","item_id":"missing"}]:
            self.assertEqual(self.request("/api/ideas","POST",payload)[0],400)
        self.assertEqual(self.request("/api/items/arxiv:2303.04137","PATCH",{"reading":[]})[0],400)
        self.assertEqual(self.request("/api/items/arxiv:2303.04137","PATCH",{"saved":"yes"})[0],400)
        self.assertEqual(self.request("/api/settings","PATCH",{"interval_minutes":1})[0],400)
        self.assertEqual(self.request("/api/settings","PATCH",{"auto_sync":False},{"Origin":"https://example.com"})[0],400)
        self.assertEqual(self.request("/api/sources/corl","PATCH",{"enabled":True})[0],400)
    def test_preferences_session_and_backup(self):
        self.assertEqual(self.request("/api/settings","PATCH",{"focus":["world"],"auto_sync":False})[0],200)
        self.assertEqual(storage.settings()["focus"],["world"])
        self.assertEqual(self.request("/api/session","POST",{"day":"2026-11-04","step":2})[0],200)
        status,data=self.request("/api/export")
        self.assertEqual(status,200)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertIn("research-library.json",z.namelist())
            exported=json.loads(z.read("research-library.json"))
            self.assertEqual(exported["settings"]["focus"],["world"])
    def test_real_http_state_and_static(self):
        status,state=self.request("/api/state")
        self.assertEqual(status,200); self.assertEqual(len(state["topics"]),8)
        self.assertIn("recommended",state)
        self.assertEqual(self.request("/")[0],200)
        self.assertEqual(self.request("/%2e%2e/app/server.py")[0],404)
    def test_source_failure_retains_existing_data(self):
        before=len(storage.all_items())
        with storage.db() as c:
            c.execute("UPDATE sources SET enabled=0")
            c.execute("UPDATE sources SET enabled=1,last_attempt=NULL WHERE id='arxiv'")
        with patch("app.collectors.arxiv",side_effect=RuntimeError("fixture network unavailable")):
            self.assertTrue(collectors.start_sync())
            self.assertTrue(collectors.LOCK.acquire(timeout=5))
            collectors.LOCK.release()
        self.assertEqual(len(storage.all_items()),before)
        source=next(s for s in storage.source_states() if s["id"]=="arxiv")
        self.assertIn("fixture network unavailable",source["error"])
        self.assertFalse(collectors.state()["running"])
    def test_mobile_commit_http_round_trip_and_conflict(self):
        target='arxiv:2303.04137'
        original=storage.get_item(target)
        command={'id':'http-mobile-1234567890','kind':'item','target':target,'base':{'notes':original['notes']},'changes':{'notes':'Native phone draft'}}
        self.assertEqual(self.request('/api/mobile/commit','POST',command)[0],200)
        self.assertEqual(self.request('/api/mobile/commit','POST',command)[0],200)
        command['id']='http-stale-1234567890';command['changes']['notes']='Stale overwrite'
        self.assertEqual(self.request('/api/mobile/commit','POST',command)[0],409)
        self.assertEqual(storage.get_item(target)['notes'],'Native phone draft')

    def test_integration_export_routes(self):
        status,raw=self.request('/api/integrations/export?target=zotero&scope=all')
        self.assertEqual(status,200);self.assertIn(b'TY  - UNPB',raw)
        for target in ['notion','obsidian']:
            status,raw=self.request('/api/integrations/export?target='+target+'&scope=all')
            self.assertEqual(status,200)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:self.assertIn('Home.md',z.namelist())
        self.assertEqual(self.request('/api/integrations/export?target=unknown')[0],400)
        self.assertEqual(self.request('/api/integrations/export?target=zotero&scope=unknown')[0],400)
if __name__=="__main__": unittest.main()
