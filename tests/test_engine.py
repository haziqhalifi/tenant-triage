import json
import tempfile
import unittest
from unittest.mock import patch
from config import Config
from engine import Engine
from adapters import Adapters
from app import process_update


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Config(demo=True, db=self.temp.name + '/test.sqlite3')
        self.engine = Engine(self.config)

    def tearDown(self):
        self.engine.db.close()
        self.temp.cleanup()

    def send(self, text, uid='1'):
        return self.engine.receive(uid, self.config.tenant, text)

    def test_followup_escalates_same_case_and_acknowledges(self):
        first = self.send('The kitchen sink is leaking.')
        self.assertEqual(self.engine.ticket(first['ticket_id'])['status'], 'waiting_on_tenant')
        second = self.send('The water is spreading and getting worse.', '2')
        self.assertEqual(first['ticket_id'], second['ticket_id'])
        ticket = self.engine.ticket(first['ticket_id'])
        self.assertEqual(ticket['urgency'], 'high')
        self.assertFalse(ticket['question'])
        self.engine.acknowledge(ticket['id'], self.config.manager)
        result = self.send('/status', '3')
        self.assertIn('has acknowledged', result['reply'])
        self.assertEqual(len(self.engine.snapshot()['tickets']), 1)

    def test_duplicate_delivery_has_no_extra_side_effects(self):
        first = self.send('AC not cold')
        before = self.engine.snapshot()
        duplicate = self.send('AC not cold')
        self.assertEqual(first, duplicate)
        self.assertEqual(before, self.engine.snapshot())

    def test_email_failure_is_persisted_and_retry_is_local(self):
        self.engine.adapter.fail_next_email = True
        self.send('The leak is spreading')
        failed = [a for a in self.engine.snapshot()['actions'] if a['status'] == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['kind'], 'email')
        self.engine.dispatch(failed[0]['id'])
        retried = next(a for a in self.engine.snapshot()['actions'] if a['id'] == failed[0]['id'])
        self.assertEqual(retried['status'], 'simulated')
        self.assertEqual(retried['attempts'], 2)

    def test_authorization_and_repeated_acknowledgement(self):
        with self.assertRaises(PermissionError):
            self.engine.receive('x', 'stranger', 'leak')
        ticket = self.send('AC not cold')['ticket_id']
        with self.assertRaises(PermissionError):
            self.engine.acknowledge(ticket, self.config.tenant)
        self.engine.acknowledge(ticket, self.config.manager)
        count = len(self.engine.snapshot()['actions'])
        self.engine.acknowledge(ticket, self.config.manager)
        self.assertEqual(count, len(self.engine.snapshot()['actions']))

    def test_crisis_overrides_model_and_cannot_be_downgraded(self):
        result = self.send('Water reaching the socket; sparks')
        ticket = self.engine.ticket(result['ticket_id'])
        self.assertEqual(ticket['urgency'], 'crisis')
        self.assertEqual(ticket['status'], 'escalated')
        self.assertIn('Do not wait', result['reply'])
        self.send('It is contained now', '2')
        self.assertEqual(self.engine.ticket(ticket['id'])['urgency'], 'crisis')

    def test_model_failure_saves_and_escalates(self):
        with patch.object(self.engine.adapter, 'classify', side_effect=RuntimeError('provider unavailable')):
            result = self.send('Something broke')
        self.assertEqual(self.engine.ticket(result['ticket_id'])['status'], 'escalated')
        self.assertIn('unavailable', result['reply'])

    def test_unknown_followup_hands_off_after_one_question(self):
        result = self.send('Something is wrong')
        self.send('Not sure', '2')
        ticket = self.engine.ticket(result['ticket_id'])
        self.assertEqual(ticket['status'], 'escalated')
        self.assertFalse(ticket['question'])

    def test_close_then_new_report_creates_new_ticket(self):
        first = self.send('AC not cold')['ticket_id']
        self.engine.acknowledge(first, self.config.manager, close=True)
        second = self.send('The sink is leaking', '2')['ticket_id']
        self.assertNotEqual(first, second)

    def test_restart_retains_deduplication_and_marks_uncertain_sends(self):
        result = self.send('AC not cold')
        with self.engine.db:
            self.engine.db.execute("UPDATE actions SET status='sending' WHERE kind='telegram'")
        self.engine.db.close()
        self.engine = Engine(self.config)
        self.engine.recover()
        self.assertEqual(self.send('AC not cold'), result)
        self.assertTrue(any(a['status'] == 'uncertain' for a in self.engine.snapshot()['actions']))

    def test_lease_is_always_human_review(self):
        result = self.send('Can I break my lease?')
        self.assertEqual(self.engine.ticket(result['ticket_id'])['status'], 'escalated')

    def test_openrouter_adapter_validates_response(self):
        self.config.demo = False
        self.config.openrouter_key = 'test-key'
        self.config.model = 'openai/gpt-4o-mini'
        assessment = {'issue_type': 'hvac', 'urgency': 'medium', 'summary': 'AC not cold', 'question': '', 'needs_human': False}
        with patch('adapters.request', return_value={'choices':[{'message':{'content':json.dumps(assessment)}}]}) as network:
            self.assertEqual(Adapters(self.config).classify([{'role':'tenant','text':'AC not cold'}]), assessment)
            self.assertEqual(network.call_args.args[0], 'https://openrouter.ai/api/v1/chat/completions')
        with patch('adapters.request', return_value={'choices':[{'message':{'content':'{"urgency":"banana"}'}}]}):
            with self.assertRaises(ValueError):
                Adapters(self.config).classify([])

    def test_telegram_private_photo_and_callback_routes(self):
        update = {'update_id': 42, 'message': {'chat': {'id': self.config.tenant, 'type': 'private'},
                 'caption': 'The sink is leaking', 'photo': [{'file_id': 'small'}, {'file_id': 'large'}]}}
        process_update(self.engine, update)
        ticket = self.engine.snapshot()['tickets'][0]
        self.assertEqual(self.engine.snapshot()['messages'][0]['photo'], 'large')
        with patch.object(self.engine.adapter, 'telegram') as telegram:
            process_update(self.engine, {'callback_query': {'id':'cb1', 'from':{'id':self.config.manager}, 'data':'ack:'+ticket['id']}})
            self.assertEqual(telegram.call_args.args[0], 'answerCallbackQuery')
        self.assertEqual(self.engine.ticket(ticket['id'])['status'], 'acknowledged')


if __name__ == '__main__':
    unittest.main()
