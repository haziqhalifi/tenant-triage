import json
import tempfile
import unittest
from config import Config
from engine import Engine
from recording_demo import prepare, WORSENING


class RecordingTests(unittest.TestCase):
    def test_script_end_to_end(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Config(demo=True, db=folder+'/recording.db'))
            try:
                ids = prepare(engine)
                self.assertNotEqual(ids['leak'], ids['ac'])
                self.assertEqual(engine.ticket(ids['leak'])['status'], 'open')
                self.assertEqual(engine.ticket(ids['ac'])['status'], 'open')
                result = engine.receive('worsening', engine.c.tenant, WORSENING)
                self.assertEqual(result['ticket_id'], ids['leak'])
                self.assertEqual(engine.ticket(ids['leak'])['urgency'], 'crisis')
                self.assertEqual(engine.ticket(ids['ac'])['urgency'], 'medium')
                engine.receive('switch-ac', engine.c.tenant, '/case '+ids['ac'])
                engine.receive('choose', engine.c.tenant, '1')
                schedule = engine.schedule(ids['ac'])
                self.assertEqual(schedule['state'], 'awaiting_approval')
                slot = schedule['selected']
                self.assertIsNone(engine.query('SELECT booked_by FROM inspection_slots WHERE id=?', (slot,))[0]['booked_by'])
                engine.scheduling_action(ids['ac'], engine.c.manager, 'approve', schedule['revision'])
                self.assertEqual(engine.schedule(ids['ac'])['state'], 'booked')
                self.assertEqual(engine.query('SELECT booked_by FROM inspection_slots WHERE id=?', (slot,))[0]['booked_by'], ids['ac'])
                self.assertTrue(all(a['status'] in ['simulated', 'recorded'] for a in engine.snapshot()['actions']))
            finally:
                engine.db.close()

    def test_slots_cannot_bypass_intake(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Config(demo=True, db=folder+'/test.db'))
            try:
                tid = engine.receive('initial', engine.c.tenant, 'AC not cold')['ticket_id']
                engine.receive('slots', engine.c.tenant, '/slots')
                self.assertIsNone(engine.schedule(tid))
                self.assertEqual(engine.ticket(tid)['status'], 'waiting_on_tenant')
            finally:
                engine.db.close()
