"""Persistent state machine and transactional outbox for maintenance coordination."""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from adapters import Adapters, LEVELS


def now():
    return datetime.now(timezone.utc).isoformat()


class Engine:
    def __init__(self, config, adapter=None):
        self.c = config
        self.adapter = adapter or Adapters(config)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(config.db, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY, chat_id TEXT, unit TEXT, issue_type TEXT, urgency TEXT,
                summary TEXT, question TEXT, status TEXT, needs_human INTEGER,
                due_at TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, ticket_id TEXT, role TEXT, text TEXT, photo TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY, ticket_id TEXT, kind TEXT, payload TEXT, status TEXT,
                attempts INTEGER DEFAULT 0, error TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS updates (id TEXT PRIMARY KEY, result TEXT);
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        ''')

    def query(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def ticket(self, ticket_id):
        rows = self.query('SELECT * FROM tickets WHERE id=?', (ticket_id,))
        return rows[0] if rows else None

    def queue(self, ticket_id, kind, payload):
        aid = str(uuid.uuid4())
        self.db.execute('INSERT INTO actions VALUES (?,?,?,?,?,0,NULL,?,?)',
                        (aid, ticket_id, kind, json.dumps(payload), 'pending', now(), now()))
        return aid

    def reply(self, ticket_id, text):
        self.db.execute('INSERT INTO messages(ticket_id,role,text,created_at) VALUES (?,?,?,?)',
                        (ticket_id, 'agent', text, now()))
        self.queue(ticket_id, 'telegram', {'chat_id': self.c.tenant, 'text': text})

    def receive(self, update_id, chat_id, text, photo=None):
        with self.lock:
            if str(chat_id) != self.c.tenant:
                raise PermissionError('This private chat is not registered to the demo property.')
            text = text.strip()
            if not text and not photo:
                raise ValueError('Send a maintenance message or photo.')
            if len(text) > 4000:
                raise ValueError('Please keep the message under 4,000 characters.')
            seen = self.query('SELECT result FROM updates WHERE id=?', (str(update_id),))
            if seen:
                return json.loads(seen[0]['result'])
            rows = self.query("SELECT * FROM tickets WHERE chat_id=? AND status!='closed' ORDER BY created_at DESC LIMIT 1", (str(chat_id),))
            previous = rows[0] if rows else None
            if text.lower() in ['/start', '/help']:
                result = {'reply': 'Send a maintenance report and optional photo. /status checks your active case. '
                          'Follow-up messages update that case until the manager closes it.'}
                with self.db:
                    self.queue(None, 'telegram', {'chat_id': self.c.tenant, 'text': result['reply']})
                    self.db.execute('INSERT INTO updates VALUES (?,?)', (str(update_id), json.dumps(result)))
                self.dispatch()
                return result
            if text.lower() in ['/status', 'status', 'any update?', 'any update']:
                with self.db:
                    response = self.status_text(previous) if previous else 'You have no active maintenance case. Send a message to open one.'
                    self.reply(previous['id'] if previous else None, response)
                    result = {'reply': response, 'ticket_id': previous['id'] if previous else None}
                    self.db.execute('INSERT INTO updates VALUES (?,?)', (str(update_id), json.dumps(result)))
                self.dispatch()
                return result
            tid = previous['id'] if previous else 'TKT-' + uuid.uuid4().hex[:8].upper()
            history = self.query('SELECT role,text FROM messages WHERE ticket_id=? ORDER BY id DESC LIMIT 16', (tid,))[::-1]
            history.append({'role': 'tenant', 'text': text or 'Photo attached; please ask me for details.'})
            assessment_failed = False
            try:
                assessment = self.adapter.classify(history, previous, photo)
            except Exception:
                assessment_failed = True
                assessment = {'issue_type': previous['issue_type'] if previous else 'other',
                              'urgency': previous['urgency'] if previous else 'high',
                              'summary': text[:400] or 'Photo report requires human review',
                              'question': '', 'needs_human': True}
            # Explicit danger reports override model decisions; priority never drops automatically.
            if any(word in text.lower() for word in ['sparks', 'gas smell', 'on fire', 'live wire', 'water reaching the socket']):
                assessment.update(urgency='crisis', needs_human=True, question='')
            if previous and LEVELS.index(previous['urgency']) > LEVELS.index(assessment['urgency']):
                assessment['urgency'] = previous['urgency']
            if assessment['urgency'] in ['high', 'crisis']:
                assessment['question'] = ''
            if assessment['issue_type'] == 'lease':
                assessment.update(needs_human=True, question='')
            if previous and previous['needs_human']:
                assessment['needs_human'] = True
            if previous and previous['question'] and assessment['question']:
                assessment.update(needs_human=True, question='')
            status = 'escalated' if assessment['needs_human'] or assessment['urgency'] == 'crisis' else ('waiting_on_tenant' if assessment['question'] else 'open')
            if previous and previous['status'] == 'acknowledged' and assessment['urgency'] == previous['urgency']:
                status = 'acknowledged'
            hours = {'low': 48, 'medium': 48, 'high': 2, 'crisis': 0}[assessment['urgency']]
            due = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
            if previous:
                due = min(due, previous['due_at'])
            stamp = now()
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (tid, str(chat_id), self.c.unit, assessment['issue_type'], assessment['urgency'],
                     assessment['summary'], assessment['question'], status, int(assessment['needs_human']),
                     due, previous['created_at'] if previous else stamp, stamp))
                self.db.execute('INSERT INTO messages(ticket_id,role,text,photo,created_at) VALUES (?,?,?,?,?)',
                                (tid, 'tenant', text or 'Photo attached', photo, stamp))
                self.queue(tid, 'assessment', {'text': 'Human fallback: model assessment unavailable.' if assessment_failed else
                           f"{assessment['issue_type']} · {assessment['urgency']} · Property SOP v1", 'assessment': assessment})
                notify = not previous or previous['urgency'] != assessment['urgency'] or (assessment['needs_human'] and not previous['needs_human']) or (previous['question'] and not assessment['question'])
                if notify:
                    manager_text = f"{tid} | Unit {self.c.unit} | {assessment['urgency'].upper()}\n{assessment['summary']}\nStatus: {status}.\n" + (
                        'Immediate human attention required.' if hours == 0 else f'Property SOP response target: {hours} hours; this is not a repair guarantee.')
                    if assessment['question']:
                        manager_text += '\nAwaiting tenant: ' + assessment['question']
                    self.queue(tid, 'telegram', {'chat_id': self.c.manager, 'text': manager_text, 'buttons': True})
                    if assessment['urgency'] in ['high', 'crisis'] or assessment['needs_human']:
                        self.queue(tid, 'email', {'subject': f"[{assessment['urgency'].upper()}] {tid} — Unit {self.c.unit}", 'text': manager_text})
                response = f"{tid} {'updated' if previous else 'created'} for unit {self.c.unit}. "
                response += f"Priority: {assessment['urgency']}. "
                if assessment['urgency'] == 'crisis':
                    response += 'Immediate human attention is needed. Keep away from the hazard; contact local emergency services if there is immediate danger. Do not wait for this chat. '
                elif assessment['needs_human']:
                    response += 'This needs your property manager’s review. '
                else:
                    response += f'Property SOP response target: {hours} hours, not a guaranteed repair time. '
                if assessment_failed:
                    response += 'Automatic assessment is unavailable; your report has been saved for human review. '
                response += assessment['question'] or 'Use /status to check manager acknowledgement.'
                self.reply(tid, response)
                result = {'ticket_id': tid, 'reply': response}
                self.db.execute('INSERT INTO updates VALUES (?,?)', (str(update_id), json.dumps(result)))
            self.dispatch()
            return result

    def status_text(self, ticket):
        actions = self.query("SELECT status FROM actions WHERE ticket_id=? AND kind='telegram' AND json_extract(payload,'$.chat_id')=? ORDER BY created_at DESC LIMIT 1", (ticket['id'], self.c.manager))
        delivery = actions[0]['status'] if actions else 'not queued'
        return f"{ticket['id']}: {ticket['status'].replace('_', ' ')}. Priority: {ticket['urgency']}. Manager notification: {delivery}. " + (
            'Your manager has acknowledged this case.' if ticket['status'] == 'acknowledged' else 'No current manager acknowledgement recorded.'
        )

    def acknowledge(self, ticket_id, manager_id, close=False):
        with self.lock:
            if str(manager_id) != self.c.manager:
                raise PermissionError('Only the registered manager can update cases.')
            ticket = self.ticket(ticket_id)
            if not ticket:
                raise ValueError('Case not found')
            target = 'closed' if close else 'acknowledged'
            if ticket['status'] == 'closed' or ticket['status'] == target:
                return {'ticket_id': ticket_id, 'status': ticket['status']}
            with self.db:
                self.db.execute('UPDATE tickets SET status=?,updated_at=? WHERE id=?', (target, now(), ticket_id))
                text = f'{ticket_id}: Your property manager has ' + ('closed the case. Send a new report if the issue continues.' if close else 'acknowledged your report and will coordinate the next step. An appointment has not been booked yet.')
                self.db.execute('INSERT INTO messages(ticket_id,role,text,created_at) VALUES (?,?,?,?)',
                                (ticket_id, 'manager', 'Case ' + target, now()))
                self.reply(ticket_id, text)
            self.dispatch()
            return {'ticket_id': ticket_id, 'status': target}

    def dispatch(self, retry_id=None):
        with self.lock:
            if retry_id:
                with self.db:
                    # Explicit retry may duplicate Telegram delivery after an ambiguous timeout.
                    self.db.execute("UPDATE actions SET status='pending' WHERE id=? AND status IN ('failed','uncertain')", (retry_id,))
            for action in self.query("SELECT * FROM actions WHERE status='pending' ORDER BY created_at,id"):
                if action['kind'] == 'assessment':
                    with self.db:
                        self.db.execute("UPDATE actions SET status='recorded' WHERE id=?", (action['id'],))
                    continue
                with self.db:
                    self.db.execute("UPDATE actions SET status='sending',attempts=attempts+1 WHERE id=?", (action['id'],))
                try:
                    self.adapter.send(action)
                    status, error = ('simulated' if self.c.demo else 'sent'), None
                except Exception as exc:
                    # Never expose exception URLs (which may contain bot tokens).
                    status, error = 'failed', type(exc).__name__ + ': delivery was not confirmed; review and retry.'
                with self.db:
                    self.db.execute('UPDATE actions SET status=?,error=?,updated_at=? WHERE id=?', (status, error, now(), action['id']))

    def recover(self):
        with self.lock, self.db:
            self.db.execute("UPDATE actions SET status='uncertain',error='App restarted during delivery. Check recipient before retrying.' WHERE status='sending'")
        self.dispatch()

    def snapshot(self):
        with self.lock:
            return {'mode': 'demo' if self.c.demo else 'live', 'property': self.c.property, 'unit': self.c.unit,
                    'email_failure_armed': self.adapter.fail_next_email,
                    'tenant': self.c.tenant_name, 'model': 'Local rule simulation' if self.c.demo else self.c.model,
                    'tickets': self.query('SELECT * FROM tickets ORDER BY created_at DESC'),
                    'messages': self.query('SELECT * FROM messages ORDER BY id'),
                    'actions': [{**a, 'payload': json.loads(a['payload'])} for a in self.query('SELECT * FROM actions ORDER BY created_at DESC')]}
