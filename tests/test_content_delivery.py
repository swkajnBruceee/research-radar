import io,json,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
from app import storage,deep_read,frontier,public_content,attention,research_tools,reading_queue as queue

class Response(io.BytesIO):
    def __init__(self,body,length=None):
        super().__init__(body);self.headers={} if length is None else {'Content-Length':str(length)}

class DownloadTests(unittest.TestCase):
    def test_download_is_streamed_and_completed_file_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            body=b'%PDF-'+b'x'*(2*1024*1024)
            with patch.object(deep_read.urllib.request,'urlopen',return_value=Response(body,len(body))) as request:
                path=deep_read.download_pdf('https://arxiv.org/pdf/2611.12345v1',Path(directory))
                self.assertEqual(path.read_bytes(),body)
                self.assertEqual(deep_read.download_pdf('https://arxiv.org/pdf/2611.12345v1',Path(directory)),path)
                self.assertEqual(request.call_count,1)
    def test_partial_or_oversized_download_leaves_no_completed_cache(self):
        for body,length,limit in [(b'%PDF-small',300,1024),(b'%PDF-'+b'x'*2000,None,1024),(b'not a pdf',None,1024)]:
            with self.subTest(length=length),tempfile.TemporaryDirectory() as directory:
                with patch.object(deep_read,'PDF_LIMIT',limit),patch.object(deep_read.urllib.request,'urlopen',return_value=Response(body,length)):
                    with self.assertRaises(deep_read.PreparationError):deep_read.download_pdf('https://arxiv.org/pdf/2611.12345v1',Path(directory))
                self.assertEqual(list(Path(directory).iterdir()),[])

class ContentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA,storage.DB
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'test.sqlite3';storage.init();deep_read.init()
        self.report=json.loads((storage.ROOT/'content/reading-pilots/raft-v1.json').read_text())
        self.doc=json.loads((storage.ROOT/'content/reading-pilots/raft-v1-evidence.json').read_text())
        self.iid=self.report['item_id'];url=self.doc['url'].replace('/html/','/abs/')
        self.item={'id':self.iid,'title':'RAFT','url':url,'source_id':'arxiv','kind':'paper','published':'2026-11-03','updated':'2026-11-03','topics':['vla'],'summary':'public abstract'}
        storage.upsert(self.item)
        with storage.db() as c:
            c.execute('UPDATE items SET notes=?,saved=1,reading=? WHERE id=?',('PRIVATE NOTE','read',self.iid))
            c.execute('INSERT INTO reading_documents VALUES (?,?,?,?,?,?,?,?)',(self.doc['id'],self.iid,self.doc['url'],self.doc['format'],json.dumps(self.doc['passages']),storage.now(),'public.html',deep_read.signature(self.item)))
            c.execute('INSERT INTO reading_results VALUES (?,?,?)',(self.doc['id'],json.dumps(self.report),storage.now()))
    def tearDown(self):storage.DATA,storage.DB=self.old;self.temp.cleanup()
    def test_package_is_public_stable_and_includes_full_readings(self):
        first=public_content.package();self.assertEqual(first['manifest']['count'],1)
        encoded=json.dumps(first)
        self.assertNotIn('PRIVATE NOTE',encoded);self.assertNotIn('"saved"',encoded);self.assertNotIn('"notes"',encoded)
        frontier.init()
        with storage.db() as c:c.execute('INSERT INTO frontier_states VALUES (?,?,?,?)',(self.iid,'x','later',storage.now()))
        self.assertEqual(public_content.package()['version'],first['version'])
        reading=first['readings'][self.iid]
        self.assertEqual(reading['document']['passages'],self.doc['passages'])
        self.assertTrue(first['signals'][0]['reuse']['changes'])
    def test_new_version_or_incomplete_read_is_not_downloadable_as_published(self):
        bad={**self.report,'coverage':{**self.report['coverage'],'read':0}}
        with storage.db() as c:c.execute('UPDATE reading_results SET payload=?',(json.dumps(bad),))
        self.assertEqual(public_content.package()['manifest']['count'],0)
        with storage.db() as c:c.execute('UPDATE reading_results SET payload=?',(json.dumps(self.report),))
        self.assertEqual(public_content.package()['manifest']['count'],1)
        storage.upsert({**self.item,'url':self.item['url'][:-1]+'2','updated':'2026-11-04'})
        self.assertEqual(public_content.package()['manifest']['count'],0)
    def test_same_explicit_revision_survives_rss_api_date_and_url_changes(self):
        legacy={**self.item,'url':self.item['url'].removesuffix('v1'),'updated':'2026-11-04'}
        with storage.db() as c:c.execute('UPDATE reading_documents SET source_signature=?',(deep_read.signature(legacy),))
        self.assertEqual(public_content.package()['manifest']['count'],1)
        self.assertIsNotNone(deep_read.state(self.iid)['analysis'])
        queue.init();queue.register_candidates()
        task=queue.snapshot()['tasks'][0]
        self.assertEqual(task['status'],'needs_review')
        self.assertEqual(task['document_id'],self.doc['id'])
        frontier.init()
        with storage.db() as c:c.execute('INSERT OR REPLACE INTO frontier_states VALUES (?,?,?,?)',(self.iid,deep_read.signature(legacy)[:24],'seen',storage.now()))
        self.assertEqual(frontier.build(storage.all_items())['signals'][0]['status'],'seen')
        self.assertEqual(frontier.current(storage.get_item(self.iid),{'version_signature':deep_read.signature(legacy)[:24],'status':'seen'})['status'],'seen')
        self.assertEqual(storage.get_item(self.iid)['notes'],'PRIVATE NOTE')
        for url in [legacy['url'],self.item['url'].removesuffix('v1')+'v2']:
            storage.upsert({**self.item,'url':url,'updated':'2026-11-05'})
            self.assertEqual(public_content.package()['manifest']['count'],0)
    def test_public_package_order_and_version_do_not_reveal_personal_priority_triage(self):
        report=json.loads((storage.ROOT/'content/reading-pilots/supermimic-v1.json').read_text())
        doc=json.loads((storage.ROOT/'content/reading-pilots/supermimic-v1-evidence.json').read_text())
        item={**report['paper'],'source_id':'arxiv','kind':'paper'};storage.upsert(item)
        with storage.db() as c:
            c.execute('INSERT INTO reading_documents VALUES (?,?,?,?,?,?,?,?)',(doc['id'],item['id'],doc['url'],doc['format'],json.dumps(doc['passages']),storage.now(),'public.pdf',deep_read.signature(item)))
            c.execute('INSERT INTO reading_results VALUES (?,?,?)',(doc['id'],json.dumps(report),storage.now()))
        first=public_content.package();self.assertEqual(first['signals'][0]['id'],item['id'])
        with storage.db() as c:
            c.execute('INSERT OR REPLACE INTO frontier_states VALUES (?,?,?,?)',(item['id'],frontier.signature(item),'seen',storage.now()))
        self.assertNotEqual(frontier.build(storage.all_items())['signals'][0]['id'],item['id'])
        self.assertEqual(public_content.package()['version'],first['version'])
    def test_editorial_calibration_keeps_original_report_and_personal_work_unchanged(self):
        import copy
        raw=json.dumps(self.report)
        ids=list(dict.fromkeys(i for f in self.report['findings'] if f['kind'] in ['method','evidence'] for i in f['evidence_ids']))
        base=frontier.publication(self.report,self.doc['passages'],next(r for r in json.loads((storage.ROOT/'content/frontier.json').read_text()) if r['id']==self.iid))['attention']
        value={**base,'impact':dict(scope='method',support='controlled',area='training',comparison='相对整体训练路线，冻结适配器是有对照的训练方法选择。',evidence_ids=ids),'headline':'RAFT：冻结推理适配器后再学习动作'}
        attention.calibrate([dict(document_id=self.doc['id'],attention=value)])
        package=public_content.package();self.assertEqual(package['signals'][0]['attention']['impact']['rank'],2)
        versions=package['manifest']['reading_versions'];self.assertEqual(set(versions),set(package['readings']))
        self.assertEqual(package['signals'][0]['title'],value['headline'])
        with storage.db() as c:self.assertEqual(json.loads(c.execute('SELECT payload FROM reading_results').fetchone()[0]),self.report)
        self.assertEqual(storage.get_item(self.iid)['notes'],'PRIVATE NOTE')
        bad=copy.deepcopy(value);bad['impact']['compared_with']=['f'*64]
        with self.assertRaisesRegex(ValueError,'尚未完成全文精读'):attention.calibrate([dict(document_id=self.doc['id'],attention=bad)])
        self.assertEqual(public_content.package()['version'],package['version'])
    def test_cached_public_package_is_isolated_from_caller_mutation(self):
        first=public_content.package();first['signals'][0]['title']='Caller changed a copy'
        self.assertNotEqual(public_content.package()['signals'][0]['title'],'Caller changed a copy')
    def test_adoption_conditions_cannot_claim_known_inputs_without_matching_evidence(self):
        value={'requirements':[dict(label='训练数据',status='known',text='需要额外监督。',evidence_ids=[self.doc['passages'][0]['id']],quote='fabricated unsupported input')]}
        with self.assertRaises(ValueError):research_tools.adoption({**self.report,'adoption':value},self.doc['passages'])
    def test_cached_pdf_survives_extraction_failure_and_retry(self):
        paper={**self.item,'id':'arxiv:2611.12345','url':'https://arxiv.org/abs/2611.12345v1'}
        error=urllib.error.HTTPError(paper['url'],404,'no html',{},None)
        rows=[{'id':'p','location':'PDF 第 1 页','text':'Public evidence '*50}]
        with patch.object(deep_read,'fetch',side_effect=error),patch.object(deep_read.urllib.request,'urlopen',return_value=Response(b'%PDF-content')) as request:
            with patch.object(deep_read,'extract_pdf',side_effect=deep_read.PreparationError('cannot read','extraction')):
                with self.assertRaises(deep_read.PreparationError):deep_read.obtain(paper)
            with patch.object(deep_read,'extract_pdf',return_value=rows):deep_read.obtain(paper)
            self.assertEqual(request.call_count,1)

class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA,storage.DB
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'test.sqlite3';storage.init();queue.init()
        self.html=b'<article><p>'+b'Public method and experiment. '*80+b'</p></article>'
    def tearDown(self):storage.DATA,storage.DB=self.old;self.temp.cleanup()
    def add(self,number,date,title,topics):
        iid='arxiv:2611.'+number
        storage.upsert({'id':iid,'url':'https://arxiv.org/abs/2611.'+number+'v1','title':title,'source_id':'arxiv','kind':'paper','published':date,'updated':date,'topics':topics,'summary':'Public method and experiment.'})
        attention.assess(iid,0,'测试候选已完成常规重要性初筛。','Public method and experiment')
        return queue.enqueue(iid)
    def test_new_focused_method_precedes_old_ready_task_and_same_day_survey(self):
        old=self.add('10001','2026-11-04','A method',['vla'])
        with patch.object(deep_read,'fetch',return_value=self.html):queue.prepare(queue.claim_prepare('old',task_id=old))
        self.add('10003','2026-11-05','A full-stack survey',['vla'])
        newest=self.add('10002','2026-11-05','A specific method',['vla'])
        with patch.object(deep_read,'fetch',return_value=self.html):bundle=queue.claim_agent()
        self.assertEqual(bundle['task_id'],newest)
        self.assertEqual(next(t for t in queue.snapshot()['tasks'] if t['id']==old)['status'],'ready_for_agent')
        self.assertEqual(len(queue.snapshot()['tasks']),3)
    def test_permanent_failure_does_not_retry_three_times(self):
        tid=self.add('10001','2026-11-05','A method',['vla'])
        row=queue.claim_prepare('worker')
        with patch.object(deep_read,'obtain',side_effect=deep_read.PreparationError('unreadable page','unreadable_pages')):queue.prepare(row)
        task=next(t for t in queue.snapshot()['tasks'] if t['id']==tid)
        self.assertEqual(task['status'],'failed');self.assertEqual(task['attempts'],1)
        self.assertEqual(task['failure_code'],'unreadable_pages');self.assertFalse(task['retryable'])
