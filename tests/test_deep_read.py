import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import deep_read, storage, connection

class ReadingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=(storage.DATA,storage.DB)
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'test.sqlite3';storage.init();deep_read.init()
    def tearDown(self):
        storage.DATA,storage.DB=self.old;self.temp.cleanup()
    def test_article_citations_keep_parent_anchors_and_ignore_outside_text(self):
        parser=deep_read.ArticleParser()
        parser.feed('<nav><p>This must not become a paper paragraph.</p></nav><article><section id="S2"><h2>Methods</h2><div id="S2.p1"><p>The policy uses a diffusion process to produce action sequences. <script>BAD INSTRUCTION</script></p></div><h3>Experiments</h3><p>We evaluate on five tasks with fixed seeds and held-out objects.</p></section></article><p>Footer must not be included in the reading evidence.</p>')
        passages=deep_read.prepare_passages(parser.passages,'https://arxiv.org/html/2303.04137v1','html')
        self.assertEqual(len(passages),2);self.assertEqual(passages[0]['section'],'Methods')
        self.assertTrue(passages[0]['url'].endswith('#S2.p1'));self.assertNotIn('BAD',passages[0]['text'])
        self.assertEqual(passages,deep_read.prepare_passages(parser.passages,'https://arxiv.org/html/2303.04137v1','html'))
    def test_model_requires_existing_evidence_and_exact_quoted_substring(self):
        passages=[{'id':'a','text':'The policy uses a diffusion process to produce action sequences.'}]
        row={'kind':'method','text':'用扩散模型生成动作','evidence_ids':['a'],'quote':'a diffusion process to produce action sequences'}
        result={'overview':'方法解读','findings':[row],'hypotheses':[]}
        self.assertEqual(deep_read.validate_result(result,passages),result)
        for change in [{'evidence_ids':['invented']},{'quote':'This statement is fabricated and not in the source.'},{'evidence_ids':[{}]},{'evidence_ids':'a'},{'text':False},{'quote':'short'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):deep_read.validate_result({**result,'findings':[{**row,**change}]},passages)
    def test_prepared_evidence_is_invalidated_when_source_version_changes(self):
        item=storage.get_item('arxiv:2303.04137');html=b'<article><h2>Methods</h2><div id="S1.p1"><p>'+b'A policy predicts actions conditioned on observations. '*40+b'</p></div></article>'
        with patch.object(deep_read,'fetch',side_effect=[b'<a href="/abs/2303.04137v1">version</a>',html]):document_id=deep_read.obtain(item)
        first=deep_read.state(item['id']);self.assertEqual(first['document']['id'],document_id)
        backup=deep_read.export_snapshot()['documents'];self.assertEqual(backup[0]['passages'],first['document']['passages']);self.assertNotIn('raw_file',backup[0])
        with storage.db() as c:c.execute('UPDATE items SET url=? WHERE id=?',(item['url']+'v2',item['id']))
        self.assertIsNone(deep_read.state(item['id'])['document'])
    def test_unconfigured_model_does_not_start_or_create_an_analysis(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertFalse(deep_read.configured())
            with self.assertRaisesRegex(ValueError,'未配置'):deep_read.start('arxiv:2303.04137',True)
        self.assertIsNone(deep_read.state('arxiv:2303.04137')['analysis'])
    def test_pdf_passages_link_to_actual_pages(self):
        value={'pages':[{'page':3,'text':'A reliable policy must remain stable during contact transitions. '*12}]}
        import subprocess
        with patch.object(Path,'exists',return_value=True),patch.object(deep_read.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(value).encode(),b'')):
            passages=deep_read.extract_pdf(Path('/tmp/paper.pdf'),'https://arxiv.org/pdf/2303.04137v1')
        self.assertTrue(all(p['url'].endswith('#page=3') for p in passages));self.assertEqual(passages[0]['location'],'PDF 第 3 页')
    def pilot(self):
        item=storage.get_item('arxiv:2303.04137')
        with storage.db() as c:c.execute('UPDATE items SET notes=? WHERE id=?',('我的原始笔记',item['id']))
        html=b'<article><h2>Method</h2><p>'+b'A policy predicts reliable actions. '*50+b'</p><p>'+b'Experiments compare matched conditions. '*50+b'</p></article>'
        with patch.object(deep_read,'fetch',side_effect=[b'/abs/2303.04137v1',html]):digest=deep_read.obtain(item)
        doc=deep_read.state(item['id'])['document'];ids=[p['id'] for p in doc['passages']]
        return {'item_id':item['id'],'document_id':digest,'source_url':doc['url'],'mode':'agent_pilot','review_status':'needs_review','overview':'精读试跑','coverage':{'read':len(ids),'total':len(ids),'evidence_ids':ids},'findings':[{'kind':'method','text':'证据草稿','quote':'predicts reliable actions','evidence_ids':[ids[0]]}],'hypotheses':[]}
    def test_agent_pilot_publishes_idempotently_without_changing_notes(self):
        report=self.pilot()
        deep_read.import_agent_report(report);deep_read.import_agent_report(report)
        state=deep_read.state(report['item_id'])
        self.assertEqual(state['analysis'],report)
        self.assertEqual(storage.get_item(report['item_id'])['notes'],'我的原始笔记')
        with self.assertRaisesRegex(ValueError,'未覆盖'):deep_read.import_agent_report({**report,'overview':'不同的报告'})
        self.assertEqual(deep_read.state(report['item_id'])['analysis'],report)
    def test_agent_pilot_rejects_stale_source_and_fabricated_citations(self):
        report=self.pilot()
        bad={**report,'findings':[{**report['findings'][0],'quote':'This was never present in the paper'}]}
        with self.assertRaisesRegex(ValueError,'引文'):deep_read.import_agent_report(bad)
        self.assertIsNone(deep_read.state(report['item_id'])['analysis'])
        with storage.db() as c:c.execute('UPDATE items SET url=? WHERE id=?',('https://arxiv.org/abs/2303.04137v2',report['item_id']))
        with self.assertRaisesRegex(ValueError,'版本'):deep_read.import_agent_report(report)
    def test_agent_pilot_cannot_cite_unread_passages_or_invent_coverage(self):
        report=self.pilot();ids=report['coverage']['evidence_ids']
        for coverage in [{'read':1,'total':2,'evidence_ids':[ids[1]]},{'read':3,'total':2,'evidence_ids':ids},{'read':2,'total':2,'evidence_ids':[ids[0],ids[0]]}]:
            with self.subTest(coverage=coverage),self.assertRaises(ValueError):deep_read.import_agent_report({**report,'coverage':coverage})
        self.assertIsNone(deep_read.state(report['item_id'])['analysis'])
    def test_pairing_exposes_no_access_code_or_private_library(self):
        (storage.DATA/'access-code.txt').write_text('secret-test-code')
        with patch.object(connection,'local_hostname',return_value='research-mac.local'),patch('app.access.local_ipv4',return_value=['127.0.0.1','10.1.2.3']):
            value=connection.pairing(8765)
        self.assertEqual(value['address'],'http://research-mac.local:8765/')
        self.assertNotIn('secret-test-code',json.dumps(value));self.assertNotIn('items',value)
        self.assertEqual(connection.identity(),value['id'])

if __name__=='__main__':unittest.main()
