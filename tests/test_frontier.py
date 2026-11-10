import json,tempfile,unittest,uuid
from pathlib import Path
from app import frontier,mobile,storage,deep_read
from app.server import idea_payload

class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=(storage.DATA,storage.DB)
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'test.sqlite3';storage.init()
        review=json.loads((storage.ROOT/'content/frontier.json').read_text())[0]
        self.item={'id':review['id'],'title':'RAFT','url':review['source_url'],'source_id':'arxiv','kind':'paper','published':'2026-11-03','updated':'2026-11-03','summary':'Reasoning aligned fine tuning','topics':['vla','imitation']}
        storage.upsert(self.item)
        deep_read.init()
        evidence=json.loads((storage.ROOT/'content/reading-pilots/raft-v1-evidence.json').read_text())
        report=json.loads((storage.ROOT/'content/reading-pilots/raft-v1.json').read_text())
        with storage.db() as c:
            c.execute('INSERT INTO reading_documents VALUES (?,?,?,?,?,?,?,?)',(evidence['id'],self.item['id'],evidence['url'],evidence['format'],json.dumps(evidence['passages']),evidence['fetched'],'public-fixture.html',deep_read.signature(self.item)))
            c.execute('INSERT INTO reading_results VALUES (?,?,?)',(evidence['id'],json.dumps(report),storage.now()))
    def tearDown(self):storage.DATA,storage.DB=self.old;self.temp.cleanup()
    def signal(self):return next(r for r in frontier.build(storage.all_items())['signals'] if r['id']==self.item['id'])
    def command(self,status='later'):
        row=self.signal()
        return {'id':str(uuid.uuid4()),'kind':'frontier','target':row['id'],'base':{k:row[k] for k in ['status','version_signature']},'changes':{'status':status}}
    def test_recent_increments_are_specific_and_foundations_never_enter_feed(self):
        result=frontier.build(storage.all_items());self.assertEqual(len(result['signals']),1)
        row=result['signals'][0];self.assertTrue(row['reviewed']);self.assertIn('RAFT',row['title']);self.assertTrue(row['before'] and row['after'] and row['evidence'])
        self.assertEqual(row['published'],'2026-11-03')
        self.assertEqual(result['frontier_meta']['latest_date'],'2026-11-03')
    def test_review_does_not_apply_to_a_new_paper_version(self):
        command=self.command();mobile.commit(command,idea_payload)
        storage.upsert({**self.item,'url':self.item['url'][:-1]+'2','updated':'2026-11-04'})
        result=frontier.build(storage.all_items());self.assertEqual(result['signals'],[])
        self.assertEqual(result['reading_candidates'][0]['id'],self.item['id'])
        with self.assertRaises(mobile.Conflict):mobile.commit({**command,'id':str(uuid.uuid4())},idea_payload)
    def test_queue_is_idempotent_and_independent_of_paper_reading_state(self):
        before=storage.get_item(self.item['id']);command=self.command()
        receipt=mobile.commit(command,idea_payload);self.assertEqual(mobile.commit(command,idea_payload),receipt)
        self.assertEqual(self.signal()['status'],'later')
        after=storage.get_item(self.item['id']);self.assertEqual(before,after)
        self.assertEqual(frontier.snapshot_states()[0]['status'],'later')
    def test_conflicting_triage_preserves_remote_choice_and_can_be_retried(self):
        first=self.command('later');stale=self.command('dismissed');mobile.commit(first,idea_payload)
        with self.assertRaises(mobile.Conflict) as error:mobile.commit(stale,idea_payload)
        self.assertEqual(error.exception.current['status'],'later');self.assertEqual(self.signal()['status'],'later')
        restore=self.command('new');mobile.commit(restore,idea_payload);self.assertEqual(self.signal()['status'],'new')
    def test_no_unreviewed_metadata_is_promoted_to_a_claim(self):
        storage.upsert({**self.item,'id':'arxiv:2611.99999','title':'A new VLA','url':'https://arxiv.org/abs/2611.99999v1'})
        result=frontier.build(storage.all_items())
        self.assertFalse(any(r['id']=='arxiv:2611.99999' for r in result['signals']))
        self.assertTrue(any(r['id']=='arxiv:2611.99999' for r in result['reading_candidates']))
    def test_offline_bundle_contains_public_increments_with_valid_revisions(self):
        seed=json.loads((storage.ROOT/'ios/ResearchRadar/Resources/ReadingShelf.json').read_text())
        self.assertGreaterEqual(len(seed['signals']),2)
        self.assertEqual(seed['frontier_meta']['latest_date'],max(r['published'] for r in seed['signals']))
        self.assertEqual(len({r['id'] for r in seed['signals']}),len(seed['signals']))
        self.assertEqual(seed['frontier_meta']['published_count'],len(seed['signals']))
        items={r['id']:r for r in seed['items']}
        for row in seed['signals']:
            self.assertTrue(row['delta'] and row['before'] and row['after']);self.assertEqual(row['status'],'new')
            self.assertTrue(row['publication_ready'])
            self.assertEqual(row['version_signature'],frontier.signature(items[row['id']]))
            reading=seed['public_readings'][row['id']]
            self.assertEqual(frontier.publication(reading['analysis'],reading['document']['passages'],row)['title'],row['title'])
            self.assertFalse(items[row['id']]['notes'])
    def test_status_validation_rejects_missing_revisions_and_unknown_states(self):
        command=self.command();command['changes']['status']='read'
        with self.assertRaises(ValueError):mobile.commit(command,idea_payload)
        command=self.command();command['base'].pop('version_signature')
        with self.assertRaises(ValueError):mobile.commit(command,idea_payload)

    def test_editorial_abstract_alone_never_publishes_a_paper(self):
        with storage.db() as c:c.execute('DELETE FROM reading_results')
        result=frontier.build(storage.all_items())
        self.assertEqual(result['signals'],[])
        self.assertEqual(result['frontier_meta']['pending_count'],1)
        self.assertEqual(storage.get_item(self.item['id'])['summary'],self.item['summary'])

    def test_incomplete_read_or_incorrect_quote_blocks_publication(self):
        with storage.db() as c:original=json.loads(c.execute('SELECT payload FROM reading_results').fetchone()[0])
        for alteration in ['coverage','quote','brief']:
            bad=json.loads(json.dumps(original))
            if alteration=='coverage':bad['coverage']['read']-=1
            elif alteration=='quote':bad['findings'][0]['quote']='A fabricated quote absent from the original paper.'
            else:bad['frontier_brief']={'title':''}
            with storage.db() as c:c.execute('UPDATE reading_results SET payload=?',(json.dumps(bad),))
            self.assertEqual(frontier.build(storage.all_items())['signals'],[])

if __name__=='__main__':unittest.main()
