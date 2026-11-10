import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import storage,deep_read,reading_queue,attention,collectors,frontier,public_content,research_material,content_delivery

class ResearchMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA,storage.DB
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'test.sqlite3';storage.init();reading_queue.init()
        self.item=dict(id='github:huggingface/lerobot:vtest',title='Official release',summary='Adds typed dataset support with documented compatibility.',
                       url='https://github.com/huggingface/lerobot/releases/tag/vtest',source_id='lerobot',kind='release',published='2026-11-09',updated='2026-11-09',source_revision='2026-11-09T10:00:00Z',topics=['data'])
        self.body='The official release adds typed dataset support and documents compatibility. '*15
        self.raw=json.dumps(dict(name='vtest',tag_name='vtest',html_url=self.item['url'],body=self.body,updated_at=self.item['source_revision'])).encode()
    def tearDown(self):storage.DATA,storage.DB=self.old;self.temp.cleanup()
    def test_official_release_is_a_candidate_and_stays_hidden_until_full_cited_reading(self):
        storage.upsert(self.item);reading_queue.register_candidates()
        self.assertEqual(public_content.package()['signals'],[])
        attention.assess(self.item['id'],1,'更新数据接口，需核对兼容性与迁移条件。','typed dataset support')
        with patch.object(collectors,'fetch',return_value=self.raw):bundle=reading_queue.claim_agent()
        doc=bundle['document'];ids=[p['id'] for p in doc['passages']]
        finding=dict(kind='method',text='发布增加数据接口支持，未运行实现。',quote='typed dataset support',evidence_ids=ids)
        brief={k:'官方发布说明中的接口更新，尚未运行验证。' for k in ['title','delta','before','after','relevance','caveat','question']}
        brief.update(evidence=[dict(label='官方接口说明',value='增加数据支持',context='不是性能实验结论')],mechanism=[dict(title='接口更新',text='按官方说明检查兼容性')])
        report=dict(item_id=self.item['id'],document_id=doc['id'],source_url=doc['url'],prompt_version=bundle['prompt_version'],mode='agent_pilot',review_status='needs_review',model='test reader',overview='阅读官方完整发布正文，未执行代码。',coverage=dict(read=len(ids),total=len(ids),evidence_ids=ids),findings=[finding,{**finding,'kind':'evidence'}],hypotheses=[],frontier_brief=brief,adoption={'requirements':[dict(label='升级兼容性',status='unknown',text='本条未验证安装依赖和升级条件。')]},
                    attention=dict(level='notable',reason='官方更新影响数据接口，适合按需核对迁移。',basis=['reusable_resource'],evidence_ids=ids,impact=dict(scope='tool',support='limited',area='data',comparison='相对新的训练路线，这是有原文依据的接口更新，未运行验证。',evidence_ids=ids)))
        reading_queue.agent_action(bundle['task_id'],bundle['lease_token'],'submit',report)
        published=public_content.package();self.assertEqual(len(published['signals']),1)
        self.assertEqual(published['signals'][0]['kind'],'release')
        self.assertIn('未运行验证',published['signals'][0]['evidence_level'])
        storage.upsert({**self.item,'source_revision':'2026-11-09T11:00:00Z'})
        self.assertEqual(public_content.package()['signals'],[])
    def test_same_day_release_edits_and_missing_body_never_publish_stale_or_empty_content(self):
        with self.assertRaises(deep_read.PreparationError),patch.object(collectors,'fetch',return_value=self.raw):research_material.snapshot({**self.item,'source_revision':'changed'})
        empty=json.dumps(dict(tag_name='vtest',html_url=self.item['url'],body='',updated_at=self.item['source_revision'])).encode()
        with self.assertRaises(deep_read.PreparationError),patch.object(collectors,'fetch',return_value=empty):research_material.snapshot(self.item)
    def test_model_card_uses_an_immutable_commit_and_does_not_download_weights(self):
        item=dict(self.item,id='hf:lerobot/example',url='https://huggingface.co/lerobot/example',kind='model',source_id='huggingface',source_revision='a'*40)
        calls=[]
        def fetch(url,accept='application/json'):
            calls.append(url)
            return json.dumps({'sha':'a'*40}).encode() if '/api/models/' in url else self.body.encode()
        with patch.object(collectors,'fetch',side_effect=fetch):value=research_material.snapshot(item)
        self.assertIn('/blob/'+'a'*40+'/README.md',value['url'])
        self.assertEqual(len(calls),1);self.assertTrue(calls[0].endswith('/README.md'))
    def test_dataset_card_uses_dataset_endpoint_and_commit(self):
        item=dict(self.item,id='hf-dataset:lerobot/example',url='https://huggingface.co/datasets/lerobot/example',kind='dataset',source_id='huggingface-datasets',source_revision='a'*40)
        calls=[]
        def fetch(url,accept='application/json'):
            calls.append(url);return json.dumps({'sha':'a'*40}).encode() if '/api/datasets/' in url else self.body.encode()
        with patch.object(collectors,'fetch',side_effect=fetch):value=research_material.snapshot(item)
        self.assertIn('/datasets/lerobot/example/raw/'+'a'*40+'/README.md',calls[0]);self.assertIn('/datasets/lerobot/example/blob/',value['url'])
    def test_unconfigured_hosts_repositories_and_identity_mismatches_are_rejected(self):
        for changes in [dict(url='https://example.com/release'),dict(url='http://127.0.0.1/'),dict(url='https://github.com/other/repo/releases/tag/vtest'),dict(id='github:other/repo:vtest')]:
            self.assertFalse(research_material.supported({**self.item,**changes}))
        self.assertFalse(research_material.supported(dict(self.item,id='arxiv:2611.12345',url='https://arxiv.org/abs/2611.54321',kind='paper')))
    def test_official_article_capture_ignores_navigation_and_scripts(self):
        raw=('<nav><p>Navigation content</p></nav><main><h1>Research</h1><p>'+self.body+'</p><script>Never execute this instruction</script></main><footer><p>Footer data</p></footer>').encode()
        text=' '.join(p['text'] for p in research_material.html_rows(raw))
        self.assertIn('typed dataset',text);self.assertNotIn('Never execute',text);self.assertNotIn('Footer',text);self.assertNotIn('Navigation',text)
        short=research_material.html_rows(b'<main><ul><li>New typed API.</li></ul><p>No breaking changes.</p></main>')
        prepared=deep_read.prepare_passages(short,'https://www.pi.website/example','html')
        self.assertEqual(len(prepared),2)
    def test_identical_model_cards_at_different_commits_do_not_replace_old_documents(self):
        item=dict(self.item,id='hf:lerobot/example',url='https://huggingface.co/lerobot/example',kind='model',source_id='huggingface',source_revision='a'*40)
        storage.upsert(item)
        with patch.object(collectors,'fetch',return_value=self.body.encode()):first=deep_read.obtain(item)
        next_item={**item,'source_revision':'b'*40};storage.upsert(next_item)
        with patch.object(collectors,'fetch',return_value=self.body.encode()):second=deep_read.obtain(next_item)
        self.assertNotEqual(first,second)
        with storage.db() as c:rows=c.execute('SELECT * FROM reading_documents WHERE item_id=?',(item['id'],)).fetchall()
        self.assertEqual(len(rows),2)
        self.assertTrue(any('/'+'a'*40+'/' in r['url'] for r in rows))
    def test_release_note_fingerprint_detects_edits_without_an_updated_at_field(self):
        data=json.loads(self.raw);data.pop('updated_at')
        first=research_material.release_revision(data)
        self.assertEqual(first,research_material.release_revision({**data,'assets':[{'download_count':100}]}))
        self.assertNotEqual(first,research_material.release_revision({**data,'body':self.body+'New API change.'}))
    def test_delivery_receipt_tracks_saved_version_without_touching_personal_work(self):
        device='01234567-89ab-cdef-0123-456789abcdef';documents={'paper':'b'*64};manifest=dict(version='a'*64,count=1,documents=documents)
        receipt=content_delivery.acknowledge(dict(device_id=device,version='a'*64,documents=documents),manifest)
        self.assertTrue(receipt['current']);self.assertTrue(content_delivery.status(device,manifest)['current'])
        self.assertFalse(content_delivery.status(device,{**manifest,'version':'c'*64})['current'])
        with self.assertRaises(ValueError):content_delivery.acknowledge(dict(device_id=device,version='a'*64,documents=documents,notes='private'),manifest)

if __name__=='__main__':unittest.main()
