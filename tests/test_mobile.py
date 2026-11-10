import tempfile
import unittest
from pathlib import Path
from app import mobile,storage
from app.server import idea_payload
class MobileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA,storage.DB
        storage.DATA=Path(self.temp.name);storage.DB=storage.DATA/'test.sqlite3';storage.init()
    def tearDown(self):
        storage.DATA,storage.DB=self.old;self.temp.cleanup()
    def item_command(self):
        target='arxiv:2406.09246'
        return {'id':'command-1234567890','kind':'item','target':target,'base':storage.get_item(target),'changes':{'notes':'Phone draft'}}
    def test_offline_note_replay_is_idempotent(self):
        command=self.item_command();first=mobile.commit(command,idea_payload)
        self.assertEqual(mobile.commit(command,idea_payload),first)
        self.assertEqual(storage.get_item(command['target'])['notes'],'Phone draft')
        with storage.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM mobile_receipts').fetchone()[0],1)
        command['changes']['notes']='Different payload'
        with self.assertRaises(ValueError):mobile.commit(command,idea_payload)
    def test_conflicts_do_not_overwrite_remote_or_other_fields(self):
        command=self.item_command()
        with storage.db() as c:c.execute('UPDATE items SET notes=? WHERE id=?',('Mac edited',command['target']))
        with self.assertRaises(mobile.Conflict) as result:mobile.commit(command,idea_payload)
        self.assertEqual(result.exception.current['notes'],'Mac edited')
        self.assertEqual(storage.get_item(command['target'])['notes'],'Mac edited')
        command['changes']={'saved':True}
        self.assertTrue(mobile.commit(command,idea_payload)['record']['saved'])
        self.assertEqual(storage.get_item(command['target'])['notes'],'Mac edited')
    def test_idea_create_edit_delete_and_retry(self):
        target='phone-idea-1234567890'
        command={'id':'create-1234567890','kind':'idea','target':target,'base':{'exists':False},'changes':{'title':'Test hypothesis','topic':'vla'}}
        first=mobile.commit(command,idea_payload)
        self.assertEqual(mobile.commit(command,idea_payload),first)
        change={'id':'update-1234567890','kind':'idea','target':target,'base':first['record'],'changes':{'hypothesis':'A falsifiable claim'}}
        updated=mobile.commit(change,idea_payload)['record']
        remove={'id':'delete-1234567890','kind':'idea-delete','target':target,'base':first['record'],'changes':{}}
        with self.assertRaises(mobile.Conflict):mobile.commit(remove,idea_payload)
        remove['base']=updated;mobile.commit(remove,idea_payload);mobile.commit(remove,idea_payload)
        with storage.db() as c:self.assertIsNone(c.execute('SELECT * FROM ideas WHERE id=?',(target,)).fetchone())
