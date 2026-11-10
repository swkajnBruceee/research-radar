import copy
import json
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from app import attention,collectors,frontier,reading_queue,storage


class AttentionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA,storage.DB
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'test.sqlite3';storage.init();reading_queue.init()

    def tearDown(self):
        storage.DATA,storage.DB=self.old;self.temp.cleanup()

    def item(self,iid,date,title='A differentiable world model for whole-body control'):
        storage.upsert(dict(id=iid,title=title,summary='Changes the training procedure using a shared world model.',url='https://arxiv.org/abs/'+iid.split(':')[1]+'v1',published=date,updated=date,topics=['control','world'],kind='paper',source_id='arxiv'))
        return reading_queue.enqueue(iid)

    def test_version_bound_initial_screening_accelerates_reading_without_publishing(self):
        older=self.item('arxiv:2610.99001','2026-10-20');newer=self.item('arxiv:2611.99002','2026-11-07')
        self.assertEqual(reading_queue.snapshot()['tasks'][0]['id'],newer)
        attention.assess('arxiv:2610.99001',2,'训练路线发生变化，需要优先核查全文。','shared world model')
        self.assertEqual(reading_queue.snapshot()['tasks'][0]['id'],older)
        self.assertEqual(frontier.build(storage.all_items())['signals'],[])
        self.assertEqual(storage.get_item('arxiv:2610.99001')['reading'],'unread')
        with storage.db() as c:c.execute("UPDATE items SET url=? WHERE id=?",('https://arxiv.org/abs/2610.99001v2','arxiv:2610.99001'))
        fresh=reading_queue.enqueue('arxiv:2610.99001')
        self.assertEqual(reading_queue.snapshot()['tasks'][0]['id'],newer)
        self.assertNotEqual(fresh,older)
        with self.assertRaises(ValueError):attention.assess('arxiv:2610.99001',2,'宣称重大突破，然而没有原文依据。','a fabricated quote')

    def test_shortlist_contains_adjacent_topics_and_no_personal_data(self):
        self.item('arxiv:2610.99001','2026-10-20')
        for n in range(30):
            iid='arxiv:2611.'+str(90000+n);self.item(iid,'2026-11-07','Robot learning '+str(n))
            with storage.db() as c:c.execute('UPDATE items SET topics=? WHERE id=?',(json.dumps(['vla']),iid))
        with storage.db() as c:c.execute("UPDATE items SET notes='PRIVATE NOTE DO NOT EXPORT' WHERE id='arxiv:2610.99001'")
        shortlist=reading_queue.shortlist()
        self.assertLessEqual(len(shortlist['papers']),24)
        self.assertTrue(any(r['item_id']=='arxiv:2610.99001' for r in shortlist['papers']))
        self.assertNotIn('PRIVATE NOTE',json.dumps(shortlist))

    def test_frontend_priority_requires_full_reading_and_both_method_and_experiment_sources(self):
        report=json.loads((storage.ROOT/'content/reading-pilots/supermimic-v1.json').read_text())
        passages=json.loads((storage.ROOT/'content/reading-pilots/supermimic-v1-evidence.json').read_text())['passages']
        brief=frontier.publication(report,passages)
        self.assertEqual(brief['attention']['rank'],2)
        for kind in ['unknown','method-only','coverage']:
            broken=copy.deepcopy(report)
            if kind=='unknown':broken['attention']['evidence_ids']=['fabricated']
            elif kind=='method-only':broken['attention']['evidence_ids']=[passages[15]['id']]
            else:broken['coverage']['read']-=1
            with self.assertRaises(ValueError):frontier.publication(broken,passages)
        self.assertEqual(attention.rank({'attention':brief['attention'],'status':'new'}),2)
        for state in ['seen','dismissed']:self.assertEqual(attention.rank({'attention':brief['attention'],'status':state}),0)
        self.assertEqual(attention.validate({},passages)['level'],'unassessed')

    def test_screened_routine_overrides_the_watchlist_hint(self):
        self.assertEqual(attention.queue_hint({'item_id':'arxiv:2610.28480'}),2)
        self.assertEqual(attention.queue_hint({'item_id':'arxiv:2610.28480','screening_level':0}),0)

    def screen(self,papers,level=0):
        attention.assess_many([{'item_id':p['item_id'],'source_signature':p['source_signature'],'level':level,
                               'reason':'暂未发现跨方法的实质改动，按常规候选核查。','quote':'shared world model'} for p in papers])

    def test_cannot_claim_after_skipping_or_partially_failing_screening(self):
        self.item('arxiv:2610.99001','2026-10-20');self.item('arxiv:2611.99002','2026-11-07')
        with self.assertRaisesRegex(ValueError,'先运行 shortlist'):reading_queue.claim_agent()
        batch=reading_queue.shortlist()
        self.screen(batch['papers'][:1])
        with self.assertRaisesRegex(ValueError,'还有 1 篇'):reading_queue.claim_agent()
        with self.assertRaisesRegex(ValueError,'还有 1 篇'):reading_queue.claim_agent(batch['papers'][0]['task_id'])
        self.assertEqual(reading_queue.shortlist()['batch_id'],batch['batch_id'])
        self.screen(batch['papers'][1:])
        with storage.db() as c:
            rows=reading_queue.candidates(c,['queued'])
            self.assertEqual(reading_queue.require_screening(c,rows,None)['id'],batch['batch_id'])
        html=b'<article><h2>Methods</h2><p>'+b'Public method and controlled experiments. '*80+b'</p></article>'
        with patch.object(reading_queue.deep_read,'fetch',return_value=html):bundle=reading_queue.claim_agent()
        self.assertEqual(bundle['paper']['id'],'arxiv:2611.99002')
        with storage.db() as c:self.assertTrue(c.execute('SELECT consumed FROM reading_screen_batches').fetchone()[0])
        self.assertEqual(reading_queue.shortlist()['papers'],[])
        self.assertEqual(frontier.build(storage.all_items())['signals'],[])

    def test_atomic_screening_rejects_stale_version_and_rolls_back_invalid_batch(self):
        self.item('arxiv:2610.99001','2026-10-20');self.item('arxiv:2611.99002','2026-11-07')
        batch=reading_queue.shortlist()
        with storage.db() as c:c.execute('UPDATE items SET url=url || ?',('v2',))
        with self.assertRaisesRegex(ValueError,'版本变化'):self.screen(batch['papers'])
        with storage.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM reading_attention').fetchone()[0],0)
        rows=[{'item_id':p['item_id'],'level':0,'reason':'常规候选，尚未形成重要方法变化。','quote':'shared world model'} for p in batch['papers']]
        rows[1]['quote']='fabricated evidence'
        with self.assertRaises(ValueError):attention.assess_many(rows)
        with storage.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM reading_attention').fetchone()[0],0)

    def test_assessed_priority_cannot_starve_unknown_work_and_oldest_has_reserved_capacity(self):
        for n in range(50):self.item('arxiv:2611.'+str(90000+n),'2026-11-07')
        # Many existing priorities used to fill all 24 slots indefinitely.
        for n in range(25):attention.assess('arxiv:2611.'+str(90000+n),2,'方法路线可能变化，需要核查受控比较。','shared world model')
        batch=reading_queue.shortlist();ids={r['item_id'] for r in batch['papers']}
        self.assertEqual(len(ids),24)
        self.assertTrue(all(r['screening_level'] is None for r in batch['papers']))
        self.assertIn('arxiv:2611.90025',ids)
        self.screen(batch['papers'])
        with storage.db() as c:c.execute('UPDATE reading_screen_batches SET consumed=?',(storage.now(),))
        next_batch=reading_queue.shortlist()
        self.assertEqual(len(next_batch['papers']),1)
        self.assertFalse(ids & {r['item_id'] for r in next_batch['papers']})

    def test_audit_is_read_only_and_does_not_disclose_personal_fields(self):
        self.item('arxiv:2611.99002','2026-11-07')
        with storage.db() as c:c.execute("UPDATE items SET notes='PRIVATE NOTE',reading='read'")
        audit=reading_queue.audit()
        self.assertEqual(audit['unassessed_candidates'],1)
        self.assertIsNone(audit['open_batch'])
        self.assertNotIn('PRIVATE NOTE',json.dumps(audit))
        self.assertNotIn('lease_token',json.dumps(audit))

    def test_priority_lane_requires_recorded_scope_and_does_not_consume_an_unfinished_batch(self):
        old=self.item('arxiv:2610.99001','2026-10-20');self.item('arxiv:2611.99002','2026-11-07')
        batch=reading_queue.shortlist()
        attention.assess('arxiv:2610.99001',2,'改变训练预算，需优先核查全身控制路线。','shared world model')
        with self.assertRaises(ValueError):reading_queue.claim_agent(priority_lane=True)
        attention.assess_many([dict(item_id='arxiv:2610.99001',level=2,reason='改变训练预算，需优先核查全身控制路线。',quote='shared world model',profile=dict(scope='route',area='training'))])
        html=b'<article><p>'+b'Public method and controlled experiments. '*80+b'</p></article>'
        with patch.object(reading_queue.deep_read,'fetch',return_value=html):bundle=reading_queue.claim_agent(priority_lane=True)
        self.assertEqual(bundle['task_id'],old)
        resumed=reading_queue.shortlist();self.assertEqual(resumed['batch_id'],batch['batch_id']);self.assertEqual(resumed['remaining'],1)
        reading_queue.agent_action(bundle['task_id'],bundle['lease_token'],'release')

    def test_calibrated_reach_beats_newer_local_tools_and_featured_respects_handled_groups(self):
        def signal(i,scope,area,date='2026-11-09',state='new',group=None):
            return dict(id=i,published=date,status=state,publication_ready=True,research_group=group or i,attention=dict(level='priority',impact=dict(rank=scope,support_rank=2,area=area)))
        rows=[signal('tool',1,'evaluation'),signal('route',3,'training','2026-10-20'),signal('same-release',3,'data',group='route'),signal('architecture',3,'architecture')]
        picked=attention.featured(rows)
        self.assertGreater(attention.order(rows[1]),attention.order(rows[0]))
        self.assertTrue({'route','same-release'} & {r['id'] for r in picked});self.assertLessEqual(len(picked),3)
        self.assertFalse({'route','same-release'}<={r['id'] for r in picked})
        rows[1]['status']='seen';self.assertNotIn('route',[r['id'] for r in attention.featured(rows)])

    def test_existing_bundle_is_assessed_without_rewriting_the_original_reports(self):
        raw=json.loads((storage.ROOT/'ios/ResearchRadar/Resources/ReadingShelf.json').read_text())
        self.assertTrue(all(r['attention']['level'] in ['priority','notable','routine'] for r in raw['signals']))
        self.assertIn('arxiv:2610.28480',[r['id'] for r in attention.featured(raw['signals'])])
        self.assertGreater(len({r['attention']['level'] for r in raw['signals']}),1)

    @staticmethod
    def feed(ids):
        ns='http://www.w3.org/2005/Atom';root=ET.Element('{'+ns+'}feed')
        for iid in ids:
            entry=ET.SubElement(root,'{'+ns+'}entry')
            for key,value in [('id','https://arxiv.org/abs/'+iid+'v1'),('title','Robot motion '+iid),('summary','Humanoid model-based reinforcement learning'),('published','2026-10-20'),('updated','2026-10-20')]:ET.SubElement(entry,'{'+ns+'}'+key).text=value
        return ET.tostring(root)

    def test_collector_backfills_and_tracks_a_paper_outside_the_latest_feed(self):
        starts=[]
        def fetch(url,accept):
            query=urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if 'id_list' in query:return self.feed(['2610.28480'])
            if 'start' in query:
                starts.append(int(query['start'][0]));return self.feed(['2610.'+str(50000+n) for n in range(200)])
            self.assertEqual(query['max_results'],['100'])
            self.assertIn('humanoid',query['search_query'][0]);return self.feed(['2611.99002'])
        with patch.object(collectors,'fetch',side_effect=fetch),patch.object(collectors.time,'sleep'):
            rows=collectors.arxiv();rows.commit();collectors.arxiv()
        self.assertIn('arxiv:2610.28480',{r['id'] for r in rows})
        self.assertEqual(starts,[100,300]);self.assertEqual(rows.warnings,[])

    def test_fallback_discloses_missing_coverage(self):
        def fetch(url,accept):
            if 'export.arxiv.org' in url:raise OSError('fixture offline')
            return b'<rss><channel><item><title>Robot</title><link>https://arxiv.org/abs/2611.99002</link><description>Robot</description></item></channel></rss>'
        with patch.object(collectors,'fetch',side_effect=fetch):rows=collectors.arxiv()
        self.assertEqual(len(rows),1);self.assertTrue(rows.warnings)

    def test_backfill_discovers_older_important_work_without_a_manual_watchlist(self):
        requests=[]
        def fetch(url,accept):
            query=urllib.parse.parse_qs(urllib.parse.urlparse(url).query);requests.append(query)
            return self.feed(['2610.28480'] if 'start' in query else ['2611.99002'])
        with patch.object(collectors,'fetch',side_effect=fetch),patch.object(collectors.time,'sleep'),patch.object(attention,'watchlist',return_value=[]):
            rows=collectors.arxiv()
        self.assertIn('arxiv:2610.28480',{r['id'] for r in rows})
        self.assertTrue(any('start' in q for q in requests))
        self.assertFalse(any('id_list' in q for q in requests))


if __name__=='__main__':unittest.main()
