import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import storage, integration_sync as sync

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA,storage.DB
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'test.sqlite3';storage.init();sync.init()
        with storage.db() as c:c.execute("UPDATE items SET saved=1,notes='My own note' WHERE id='arxiv:2406.09246'")
        (storage.DATA/'notion-target.json').write_text(json.dumps({'data_source_id':'fixture','url':'https://www.notion.so/fixture'}))
    def tearDown(self):
        storage.DATA,storage.DB=self.old;self.temp.cleanup()
    def test_arxiv_match_does_not_treat_arbitrary_dois_as_identifiers(self):
        self.assertEqual(sync.identifiers({'DOI':'10.1109/MEMS1670.2022'}),set())
        self.assertEqual(sync.identifiers({'DOI':'10.48550/arXiv.2406.09246'}),{'2406.09246'})
        self.assertEqual(sync.identifiers({'extra':'arXiv: 2406.09246v3'}),{'2406.09246'})
    def test_managed_property_round_trip(self):
        job=sync.jobs()[0];props=sync.wire(job['properties'])
        props['我的补充']={'rich_text':[{'text':{'content':'Keep this'}}]}
        self.assertEqual(sync.plain(props),job['properties'])
    def test_sync_checks_conflicts_before_unchanged(self):
        job=sync.jobs()[0];sync.acknowledge(job,'remote','https://www.notion.so/remote')
        props=sync.wire(job['properties']);props['标题']={'title':[{'text':{'content':'User revised title'}}]}
        with patch.dict('os.environ',{'NOTION_API_KEY':'fixture'}),patch.object(sync,'notion_request',return_value={'properties':props}) as request:
            result=sync.sync_notion()
        self.assertEqual(result['conflicts'],[job['id']]);self.assertEqual(request.call_count,1)
    def test_new_then_repeat_does_not_create_duplicate(self):
        job=sync.jobs()[0];remote={'id':'remote','url':'https://www.notion.so/remote','properties':sync.wire(job['properties'])}
        with patch.dict('os.environ',{'NOTION_API_KEY':'fixture'}),patch.object(sync,'notion_request',side_effect=[{'results':[]},remote]):
            self.assertEqual(sync.sync_notion()['new'],1)
        with patch.dict('os.environ',{'NOTION_API_KEY':'fixture'}),patch.object(sync,'notion_request',return_value=remote) as request:
            self.assertEqual(sync.sync_notion()['unchanged'],1)
        self.assertEqual(request.call_count,1)
    def test_recovery_adopts_matching_remote_without_baseline(self):
        job=sync.jobs()[0];remote={'id':'remote','url':'https://www.notion.so/remote','properties':sync.wire(job['properties'])}
        with patch.dict('os.environ',{'NOTION_API_KEY':'fixture'}),patch.object(sync,'notion_request',return_value={'results':[remote]}) as request:
            self.assertEqual(sync.sync_notion()['unchanged'],1)
        self.assertEqual(request.call_count,1);self.assertEqual(sync.jobs()[0]['state'],'synced')
    def test_zotero_preview_import_is_idempotent_and_preserves_notes(self):
        rows=[{'key':'PAPER','data':{'url':'https://arxiv.org/abs/2406.09246v3','itemType':'preprint'}},
              {'key':'PDF','data':{'itemType':'attachment','parentItem':'PAPER'}},
              {'key':'ANN','data':{'itemType':'annotation','parentItem':'PDF','annotationPageLabel':'7','annotationText':'Evidence','annotationComment':'Question','annotationPosition':'{"pageIndex":6}'}}]
        with patch.object(sync,'request_json',return_value=(rows,{'Zotero-Server-ID':'fixture'})):
            preview=sync.zotero_preview()
        self.assertEqual(preview['matched'],1);self.assertEqual(len(preview['annotations']),1)
        ids=[x['id'] for x in preview['annotations']]
        sync.import_annotations(ids);sync.import_annotations(ids)
        result=sync.annotations('arxiv:2406.09246')
        self.assertEqual(len(result),1);self.assertEqual(result[0]['page'],'7')
        self.assertIn('page=7',result[0]['source'])
        self.assertEqual(storage.get_item('arxiv:2406.09246')['notes'],'My own note')
        self.assertIn('Evidence',storage.markdown(storage.get_item('arxiv:2406.09246')))
        self.assertIn('Zotero 阅读证据',sync.jobs()[0]['properties']['研究台摘要'])
        with self.assertRaises(ValueError):sync.import_annotations(['missing'])
    def test_unconfigured_runtime_never_claims_success(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(ValueError):sync.sync_notion()
            self.assertFalse(sync.status()['notion']['runtime_configured'])
