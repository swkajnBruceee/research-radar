import json
import tempfile
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from app import storage, deep_read, attention, reading_queue as queue

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA,storage.DB
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'radar.sqlite3';storage.init();queue.init()
        self.iid='arxiv:2303.04137'
        with storage.db() as c:c.execute('UPDATE items SET url=?,notes=? WHERE id=?',('https://arxiv.org/abs/2303.04137v1','PRIVATE PERSONAL NOTES',self.iid))
        self.html=b'<article><h2>Methods</h2><p>'+b'The policy predicts reliable actions under matched conditions. '*40+b'</p></article>'
    def tearDown(self):storage.DATA,storage.DB=self.old;self.temp.cleanup()
    def task(self,tid):return next(t for t in queue.snapshot()['tasks'] if t['id']==tid)
    def ready(self):
        item=storage.get_item(self.iid)
        if not item['curated']:attention.assess(self.iid,0,'测试论文已完成初筛，继续核查全文。',item['title'])
        tid=queue.enqueue(self.iid);row=queue.claim_prepare('worker')
        with patch.object(deep_read,'fetch',return_value=self.html):queue.prepare(row)
        self.assertEqual(self.task(tid)['status'],'ready_for_agent');return tid
    def report(self,bundle):
        ids=[p['id'] for p in bundle['document']['passages']]
        finding={'kind':'method','text':'策略预测动作','quote':'predicts reliable actions','evidence_ids':ids}
        brief={k:'有依据的技术解读' for k in ['title','change_type','delta','before','after','relevance','caveat','question']}
        brief.update(evidence=[{'label':'对照','value':'作者结果','context':'固定条件评测'}],mechanism=[{'title':'方法','text':'预测动作'}])
        return {'mode':'agent_pilot','model':'test-agent','review_status':'needs_review','item_id':self.iid,'document_id':bundle['document']['id'],'source_url':bundle['document']['url'],'prompt_version':bundle['prompt_version'],'overview':'结果待核查','frontier_brief':brief,'coverage':{'read':len(ids),'total':len(ids),'evidence_ids':ids},'findings':[finding,{**finding,'kind':'evidence'}],'hypotheses':[],
                'attention':{'level':'notable','reason':'受控方法对照值得跟进，尚未改变整体训练路线。','basis':['controlled_comparison'],'evidence_ids':ids,'impact':{'scope':'method','support':'controlled','area':'control','comparison':'相对整体训练路线改变，这是有对照的局部动作方法。','evidence_ids':ids}},'adoption':{'requirements':[{'label':'数据与硬件','status':'unknown','text':'本测试材料没有核实数据与硬件条件。'}]}}
    def test_concurrent_enqueue_is_idempotent_and_no_personal_fields_are_exported(self):
        with ThreadPoolExecutor(max_workers=4) as pool:ids=list(pool.map(lambda _:queue.enqueue(self.iid),range(8)))
        self.assertEqual(len(set(ids)),1)
        row=queue.claim_prepare('one');self.assertIsNone(queue.claim_prepare('two'))
        with patch.object(deep_read,'fetch',return_value=self.html):queue.prepare(row)
        bundle=queue.claim_agent()
        self.assertNotIn('PRIVATE PERSONAL NOTES',json.dumps(bundle))
        self.assertNotIn('lease_token',json.dumps(queue.snapshot()))
        self.assertNotIn('lease_token',json.dumps(queue.export_snapshot()))
        self.assertTrue(queue.export_snapshot()['events'])
    def test_preparation_retries_with_backoff_and_stops_after_three_attempts(self):
        tid=queue.enqueue(self.iid)
        for now,attempt in [(1000,1),(1031,2),(1092,3)]:
            with patch.object(queue.time,'time',return_value=now):
                row=queue.claim_prepare('worker');self.assertEqual(row['attempts'],attempt)
                with patch.object(deep_read,'obtain',side_effect=urllib.error.URLError('offline')):queue.prepare(row)
                self.assertEqual(self.task(tid)['status'],'failed' if attempt==3 else 'queued')
        with patch.object(queue.time,'time',return_value=2000):self.assertIsNone(queue.claim_prepare('worker'))
        current=self.task(tid);queue.action(tid,'retry',current['revision'])
        self.assertEqual(self.task(tid)['attempts'],0)
    def test_cancellation_fences_inflight_preparation(self):
        tid=queue.enqueue(self.iid);row=queue.claim_prepare('worker')
        queue.action(tid,'cancel',self.task(tid)['revision'])
        with patch.object(deep_read,'fetch',return_value=self.html):queue.prepare(row)
        self.assertEqual(self.task(tid)['status'],'cancelled')
        with self.assertRaises(ValueError):queue.claim_agent(tid)
    def test_restart_expired_lease_is_reclaimed_and_old_worker_cannot_finish(self):
        tid=queue.enqueue(self.iid);old=queue.claim_prepare('old')
        with patch.object(queue.time,'time',return_value=old['lease_until']+1):new=queue.claim_prepare('new')
        self.assertNotEqual(old['lease_token'],new['lease_token'])
        with patch.object(deep_read,'fetch',return_value=self.html):queue.prepare(old)
        self.assertEqual(self.task(tid)['status'],'preparing')
        queue.prepare(new);self.assertEqual(self.task(tid)['status'],'ready_for_agent')
    def test_graceful_restart_releases_only_owned_preparation(self):
        tid=queue.enqueue(self.iid);queue.claim_prepare('owner')
        queue.release_owner('other');self.assertEqual(self.task(tid)['status'],'preparing')
        queue.release_owner('owner');self.assertEqual(self.task(tid)['status'],'queued')
    def test_new_papers_automatically_enter_pipeline_without_selection(self):
        item=storage.get_item(self.iid)
        storage.upsert({**item,'curated':0,'id':'arxiv:2611.99998','url':'https://arxiv.org/abs/2611.99998v1'})
        self.assertEqual(queue.register_candidates(),1)
        self.assertEqual(queue.register_candidates(),0)
        task=queue.snapshot()['tasks'][0]
        self.assertEqual(task['status'],'waiting_for_reader')
        # Lack of a continuous reader must not cause unbounded downloads or fake completion.
        self.assertIsNone(queue.claim_prepare('background'))
        item=storage.get_item('arxiv:2611.99998')
        attention.assess(item['id'],0,'测试论文已初筛，继续核查方法。',item['title'])
        with patch.object(deep_read,'fetch',return_value=self.html):bundle=queue.claim_agent(task['id'])
        self.assertEqual(bundle['paper']['id'],'arxiv:2611.99998')
        self.assertEqual(self.task(task['id'])['status'],'analyzing')
        with storage.db() as c:c.execute('UPDATE items SET url=? WHERE id=?',('https://arxiv.org/abs/2611.99998v2','arxiv:2611.99998'))
        self.assertEqual(queue.register_candidates(),1)
    def test_citation_failure_rolls_back_report_and_task_together(self):
        tid=self.ready();bundle=queue.claim_agent(tid);report=self.report(bundle)
        bad={**report,'findings':[{**report['findings'][0],'quote':'fabricated quotation without source'}]}
        with self.assertRaises(ValueError):queue.agent_action(tid,bundle['lease_token'],'submit',bad)
        self.assertEqual(self.task(tid)['status'],'analyzing');self.assertIsNone(deep_read.state(self.iid)['analysis'])
        queue.agent_action(tid,bundle['lease_token'],'submit',report)
        self.assertEqual(self.task(tid)['status'],'needs_review');self.assertEqual(deep_read.state(self.iid)['analysis'],report)
        current=self.task(tid);queue.action(tid,'complete',current['revision'])
        self.assertEqual(self.task(tid)['status'],'completed')
        with self.assertRaises(queue.Conflict):queue.action(tid,'cancel',current['revision'])
        queue.action(tid,'reopen',self.task(tid)['revision'])
        self.assertEqual(self.task(tid)['status'],'needs_review')
        self.assertEqual(storage.get_item(self.iid)['notes'],'PRIVATE PERSONAL NOTES')
        self.assertEqual(storage.get_item(self.iid)['reading'],'unread')
    def test_expired_or_cancelled_agent_cannot_publish(self):
        tid=self.ready();bundle=queue.claim_agent(tid);report=self.report(bundle)
        with patch.object(queue.time,'time',return_value=bundle['lease_until']+1):
            with self.assertRaises(queue.Conflict):queue.agent_action(tid,bundle['lease_token'],'submit',report)
            new=queue.claim_agent(tid)
        with self.assertRaises(queue.Conflict):queue.agent_action(tid,bundle['lease_token'],'submit',report)
        queue.action(tid,'cancel',self.task(tid)['revision'])
        with self.assertRaises(queue.Conflict):queue.agent_action(tid,new['lease_token'],'submit',report)
        self.assertIsNone(deep_read.state(self.iid)['analysis'])
    def test_source_revision_keeps_history_and_requires_new_task(self):
        tid=self.ready();bundle=queue.claim_agent(tid);report=self.report(bundle)
        with storage.db() as c:c.execute('UPDATE items SET url=? WHERE id=?',('https://arxiv.org/abs/2303.04137v2',self.iid))
        self.assertTrue(self.task(tid)['stale'])
        with self.assertRaises(queue.Conflict):queue.agent_action(tid,bundle['lease_token'],'submit',report)
        new=queue.enqueue(self.iid);self.assertNotEqual(tid,new)
        self.assertEqual(len(queue.snapshot()['tasks']),2)
    def test_useful_reading_publishes_without_user_selection_or_acceptance(self):
        from app import frontier
        with storage.db() as c:c.execute('UPDATE items SET curated=0 WHERE id=?',(self.iid,))
        tid=self.ready();bundle=queue.claim_agent(tid);report=self.report(bundle)
        bad={**report,'frontier_brief':{**report['frontier_brief'],'delta':''}}
        with self.assertRaises(ValueError):queue.agent_action(tid,bundle['lease_token'],'submit',bad)
        self.assertIsNone(deep_read.state(self.iid)['analysis'])
        queue.agent_action(tid,bundle['lease_token'],'submit',report)
        self.assertEqual(self.task(tid)['status'],'needs_review')
        signal=next(r for r in frontier.build(storage.all_items())['signals'] if r['id']==self.iid)
        self.assertTrue(signal['publication_ready'])
        self.assertEqual(storage.get_item(self.iid)['reading'],'unread')
    def test_agent_release_and_renew_preserve_the_task(self):
        tid=self.ready();bundle=queue.claim_agent(tid)
        queue.agent_action(tid,bundle['lease_token'],'renew')
        self.assertEqual(self.task(tid)['status'],'analyzing')
        queue.agent_action(tid,bundle['lease_token'],'release')
        self.assertEqual(self.task(tid)['status'],'ready_for_agent')
        self.assertNotEqual(queue.claim_agent(tid)['lease_token'],bundle['lease_token'])
    def test_existing_exact_document_report_goes_to_review(self):
        tid=self.ready();bundle=queue.claim_agent(tid)
        deep_read.import_agent_report(self.report(bundle))
        queue.agent_action(tid,bundle['lease_token'],'release')
        queue.action(tid,'cancel',self.task(tid)['revision']);queue.action(tid,'retry',self.task(tid)['revision'])
        queue.prepare(queue.claim_prepare('worker'))
        self.assertEqual(self.task(tid)['status'],'needs_review')

if __name__=='__main__':unittest.main()
