import csv
import io
import posixpath
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from app import storage, exports

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=storage.DATA,storage.DB
        storage.DATA=Path(self.temp.name); storage.DB=storage.DATA/'test.sqlite3'
        storage.init()
    def tearDown(self):
        storage.DATA,storage.DB=self.old
        self.temp.cleanup()
    def test_scope_and_ris_metadata(self):
        self.assertEqual(exports.select_items('selected'),[])
        items=exports.select_items('all')
        text=exports.ris(items).decode()
        self.assertEqual(text.count('TY  - UNPB'),6)
        self.assertIn('DO  - 10.48550/arXiv.2406.09246',text)
        self.assertNotIn('AU  - Moo Jin Kim et al.',text)
        self.assertNotIn('AB  - ',text) # foundation guides are not original abstracts
        with self.assertRaises(ValueError): exports.select_items('unknown')
        with self.assertRaises(ValueError): exports.select_items('all','missing')
    def test_source_text_cannot_inject_ris_records(self):
        item=exports.select_items('all')[0]
        item['title']='Title\nER  - \nTY  - BOOK'
        self.assertEqual(exports.ris([item]).decode().count('\r\nER  - '),1)
    def test_selected_includes_notes_and_reading(self):
        with storage.db() as c:
            c.execute("UPDATE items SET notes=? WHERE id=?",('My note','arxiv:2406.09246'))
            c.execute("UPDATE items SET reading='reading' WHERE id='arxiv:2303.04137'")
        self.assertEqual(len(exports.select_items('selected')),2)
    def test_notion_csv_and_markdown_keep_notes(self):
        item=exports.select_items('all')[0]
        item['notes']='Evidence, a quote: "yes"\nNext line'
        with zipfile.ZipFile(io.BytesIO(exports.bundle('notion',[item],[]))) as z:
            rows=list(csv.DictReader(io.StringIO(z.read('papers.csv').decode('utf-8-sig'))))
            self.assertEqual(rows[0]['我的笔记'],item['notes'])
            self.assertEqual(rows[0]['稳定ID'],item['id'])
            self.assertIn(item['notes'],z.read('Papers/'+exports.file_id('paper',item['id'])).decode())
            self.assertFalse(any('access' in n or 'sqlite' in n for n in z.namelist()))
    def test_obsidian_internal_links_resolve(self):
        items=exports.select_items('all')
        idea=dict(id='fixture',title='An idea',topic='vla',status='待调研',item_id=items[0]['id'],observation='',evidence='',hypothesis='',experiment='')
        with zipfile.ZipFile(io.BytesIO(exports.bundle('obsidian',items,[idea]))) as z:
            names=set(z.namelist())
            for name in names:
                text=z.read(name).decode()
                for link in re.findall(r'\]\(([^)]+\.md)\)',text):
                    resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),link))
                    self.assertIn(resolved,names)
            text=z.read('Papers/'+exports.file_id('paper',items[0]['id'])).decode()
            self.assertTrue(text.startswith('---\nradar_id:'))
