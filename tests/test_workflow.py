import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from config import Config
from engine import Engine
from app import process_update


class ExtendedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = Config(demo=True, db=self.tmp.name + '/test.db')
        self.e = Engine(self.c)
        self.sequence = 0

    def tearDown(self):
        self.e.db.close()
        self.tmp.cleanup()

    def send(self, text):
        self.sequence += 1
        return self.e.receive(str(self.sequence), self.c.tenant, text)

    def report(self):
        tid = self.send('/new AC not cold')['ticket_id']
        for text in ['Bedroom, blowing warm air', 'Yesterday, constant', 'Hot room, no damage', 'Cleaned filter, tomorrow afternoon']:
            self.send(text)
        return tid

    def test_separate_report_does_not_inherit_crisis_and_switch_survives_restart(self):
        first = self.send('sparks')['ticket_id']
        second = self.report()
        self.assertNotEqual(first, second)
        self.assertEqual(self.e.ticket(second)['urgency'], 'medium')
        self.assertEqual(self.e.ticket(first)['urgency'], 'crisis')
        self.send('/case ' + first)
        self.e.db.close()
        self.e = Engine(self.c)
        self.assertEqual(self.send('/status')['ticket_id'], first)
        self.assertIn(second, self.send('/cases')['reply'])

    def test_new_without_description_and_duplicate(self):
        self.send('sparks')
        result = self.e.receive('new-command', self.c.tenant, '/new')
        before = len(self.e.snapshot()['actions'])
        self.assertEqual(self.e.receive('new-command', self.c.tenant, '/new'), result)
        self.assertEqual(before, len(self.e.snapshot()['actions']))
        tid = self.send('AC not cold')['ticket_id']
        self.assertEqual(self.e.ticket(tid)['status'], 'waiting_on_tenant')

    def test_intake_waits_and_urgent_answer_bypasses_questions(self):
        tid = self.send('AC not cold')['ticket_id']
        for text in ['Bedroom', 'Yesterday', 'Room is hot']:
            self.send(text)
            self.assertEqual(self.e.ticket(tid)['status'], 'waiting_on_tenant')
            self.assertFalse([a for a in self.e.snapshot()['actions'] if a['payload'].get('chat_id') == self.c.manager])
        self.send('sparks from AC')
        self.assertEqual(self.e.ticket(tid)['status'], 'escalated')

    def test_repair_confirmation_reopens_then_closes(self):
        tid = self.report()
        with self.assertRaises(PermissionError):
            self.e.repair_update(tid, self.c.tenant, 'assign', 'Ali')
        self.e.repair_update(tid, self.c.manager, 'assign', 'Ali')
        self.e.repair_update(tid, self.c.manager, 'progress', 'Replacing capacitor')
        self.e.repair_update(tid, self.c.manager, 'complete', 'Cooling restored')
        before = len(self.e.snapshot()['actions'])
        self.e.repair_update(tid, self.c.manager, 'complete', 'Cooling restored')
        self.assertEqual(before, len(self.e.snapshot()['actions']))
        self.assertEqual(self.e.ticket(tid)['status'], 'awaiting_confirmation')
        self.send('/unresolved ' + tid)
        self.assertEqual(self.e.ticket(tid)['status'], 'in_progress')
        self.e.repair_update(tid, self.c.manager, 'complete', 'Repaired again')
        self.send('/resolved ' + tid)
        self.assertEqual(self.e.ticket(tid)['status'], 'closed')

    def test_reminders_persist_and_stop_after_confirmation(self):
        tid = self.report()
        at = datetime.now(timezone.utc) + timedelta(days=3)
        self.e.reminders(at)
        count = len(self.e.snapshot()['actions'])
        self.e.db.close()
        self.e = Engine(self.c)
        self.e.reminders(at)
        self.assertEqual(count, len(self.e.snapshot()['actions']))
        self.e.repair_update(tid, self.c.manager, 'complete', 'Fixed')
        self.send('/resolved ' + tid)
        count = len(self.e.snapshot()['actions'])
        self.e.reminders(at + timedelta(days=3))
        self.assertEqual(count, len(self.e.snapshot()['actions']))

    def test_telegram_manager_assignment(self):
        tid = self.report()
        process_update(self.e, {'update_id': 999, 'message': {'chat': {'id': self.c.manager, 'type': 'private'}, 'text': '/assign ' + tid + ' Ali'}})
        self.assertEqual(self.e.ticket(tid)['status'], 'assigned')
