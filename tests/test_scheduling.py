import json
import tempfile
import unittest
from unittest.mock import patch
from config import Config
from engine import Engine


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.c = Config(demo=True, db=self.temp.name+'/test.db')
        self.e = Engine(self.c)
        self.tid = self.e.receive('1', self.c.tenant, 'AC not cold; filter already cleaned')['ticket_id']
        self.e.receive('context', self.c.tenant, 'Bedroom. It is blowing air but not cooling.')
        for i, text in enumerate(['Since yesterday, constant.', 'Room is hot, no damage.', 'Filter cleaned. Available tomorrow.']):
            self.e.receive('intake'+str(i), self.c.tenant, text)

    def tearDown(self):
        self.e.db.close()
        self.temp.cleanup()

    def choose(self):
        s = self.e.schedule(self.tid)
        slot = json.loads(s['offered'])[0]
        self.e.scheduling_action(self.tid,self.c.tenant,'pick',s['revision'],slot)
        return s, slot

    def test_rejection_selection_approval_and_duplicate(self):
        first = self.e.schedule(self.tid)
        self.e.scheduling_action(self.tid,self.c.tenant,'other',first['revision'])
        second = self.e.schedule(self.tid)
        self.assertFalse(set(json.loads(first['offered'])) & set(json.loads(second['offered'])))
        s, slot = self.choose()
        self.assertIsNone(self.e.query('SELECT booked_by FROM inspection_slots WHERE id=?',(slot,))[0]['booked_by'])
        self.e.scheduling_action(self.tid,self.c.manager,'approve',s['revision'])
        self.assertEqual(self.e.schedule(self.tid)['state'],'booked')
        count = len(self.e.snapshot()['actions'])
        self.e.scheduling_action(self.tid,self.c.manager,'approve',s['revision'])
        self.assertEqual(len(self.e.snapshot()['actions']),count)
        self.assertIn('booked',self.e.status_text(self.e.ticket(self.tid)))

    def test_approval_requires_manager_and_tenant_selection(self):
        s = self.e.schedule(self.tid)
        with self.assertRaises(ValueError):
            self.e.scheduling_action(self.tid,self.c.manager,'approve',s['revision'])
        self.choose()
        with self.assertRaises(PermissionError):
            self.e.scheduling_action(self.tid,self.c.tenant,'approve',s['revision'])

    def test_stale_offer_and_fabricated_slot_rejected(self):
        s = self.e.schedule(self.tid)
        with self.assertRaises(ValueError):
            self.e.scheduling_action(self.tid,self.c.tenant,'pick',s['revision'],'fake')
        self.e.scheduling_action(self.tid,self.c.tenant,'other',s['revision'])
        with self.assertRaises(ValueError):
            self.e.scheduling_action(self.tid,self.c.tenant,'pick',s['revision'],json.loads(s['offered'])[0])

    def test_conflict_offers_alternatives_without_overwriting_booking(self):
        s, slot = self.choose()
        with self.e.db:
            self.e.db.execute('UPDATE inspection_slots SET booked_by=? WHERE id=?',('another-case',slot))
        self.e.scheduling_action(self.tid,self.c.manager,'approve',s['revision'])
        self.assertEqual(self.e.schedule(self.tid)['state'],'offering')
        self.assertEqual(self.e.query('SELECT booked_by FROM inspection_slots WHERE id=?',(slot,))[0]['booked_by'],'another-case')

    def test_decline_offers_alternatives(self):
        s, slot = self.choose()
        self.e.scheduling_action(self.tid,self.c.manager,'decline',s['revision'])
        self.assertNotIn(slot,json.loads(self.e.schedule(self.tid)['offered']))

    def test_natural_availability_does_not_authorize_booking(self):
        self.e.receive('2',self.c.tenant,'I am only available in the afternoon')
        s = self.e.schedule(self.tid)
        self.assertEqual(s['state'],'offering')
        for sid in json.loads(s['offered']):
            slot = self.e.query('SELECT * FROM inspection_slots WHERE id=?',(sid,))[0]
            self.assertGreaterEqual(int(slot['starts_at'][11:13]),12)
            self.assertIsNone(slot['booked_by'])

    def test_close_releases_local_reservation(self):
        s, slot = self.choose()
        self.e.scheduling_action(self.tid,self.c.manager,'approve',s['revision'])
        self.e.acknowledge(self.tid,self.c.manager,close=True)
        self.e.receive('confirm', self.c.tenant, '/resolved '+self.tid)
        self.assertIsNone(self.e.query('SELECT booked_by FROM inspection_slots WHERE id=?',(slot,))[0]['booked_by'])
        with self.assertRaises(ValueError):
            self.e.scheduling_action(self.tid,self.c.manager,'approve',s['revision'])

    def test_crisis_pauses_scheduling(self):
        s, slot = self.choose()
        self.e.receive('danger',self.c.tenant,'Sparks and smoke from the AC')
        self.assertEqual(self.e.schedule(self.tid)['state'],'needs_manager')
        with self.assertRaises(ValueError):
            self.e.scheduling_action(self.tid,self.c.manager,'approve',s['revision'])

    def test_restart_preserves_calendar_reservation(self):
        s, slot = self.choose()
        self.e.scheduling_action(self.tid,self.c.manager,'approve',s['revision'])
        self.e.db.close()
        self.e = Engine(self.c)
        self.assertEqual(self.e.schedule(self.tid)['state'],'booked')
        self.assertEqual(self.e.query('SELECT booked_by FROM inspection_slots WHERE id=?',(slot,))[0]['booked_by'],self.tid)

    def test_duplicate_text_selection_does_not_retriage(self):
        self.e.receive('choose',self.c.tenant,'1')
        count = len(self.e.snapshot()['actions'])
        self.e.receive('choose',self.c.tenant,'1')
        self.assertEqual(count,len(self.e.snapshot()['actions']))

    def test_status_does_not_call_availability_model(self):
        with patch.object(self.e.adapter,'scheduling_intent',side_effect=RuntimeError('offline')) as classify:
            result=self.e.receive('status',self.c.tenant,'/status')
            self.assertIn('offering',result['reply'])
            classify.assert_not_called()
