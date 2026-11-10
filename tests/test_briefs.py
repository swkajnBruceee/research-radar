import json
import unittest
from pathlib import Path
from app import briefs,storage

class TechnologyBriefTests(unittest.TestCase):
    def test_explanations_are_readable_without_any_library_items(self):
        rows=briefs.build([])
        self.assertEqual(len(rows),5)
        for row in rows:
            with self.subTest(method=row['id']):
                self.assertTrue(all(row.get(k) for k in ['title','tagline','why','update','mechanism','boundary','sources','checked_at']))
                self.assertEqual(row['related_ids'],[])
                self.assertEqual(row['source_item_ids'],[])
                self.assertTrue(all(s['url'].startswith('https://arxiv.org/abs/') and 'v' in s['url'].split('/')[-1] for s in row['sources']))
    def test_automatically_linked_papers_do_not_become_reviewed_technical_claims(self):
        item={'id':'arxiv:9999.12345','kind':'paper','title':'An unreviewed world model','summary':'World action model','updated':'2099-01-01'}
        first=briefs.build([]);after=briefs.build([item]);world=next(r for r in after if r['id']=='world-action')
        self.assertIn(item['id'],world['related_ids'])
        self.assertNotIn(item['id'],[s['item_id'] for s in world['sources']])
        self.assertEqual([r['update'] for r in first],[r['update'] for r in after])
        self.assertEqual([r['id'] for r in first],[r['id'] for r in after])
    def test_first_launch_bundle_matches_reviewed_public_content(self):
        source=json.loads((storage.ROOT/'content/technologies.json').read_text())
        seed=json.loads((storage.ROOT/'ios/ResearchRadar/Resources/ReadingShelf.json').read_text())
        self.assertEqual(source,seed['technology_briefs'])
        self.assertTrue(all(not i.get('notes') for i in seed['items']))
        self.assertEqual(next(r for r in source if r['id']=='generative-action')['update_label'],'方法基础')

if __name__=='__main__':unittest.main()
