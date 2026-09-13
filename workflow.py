"""Persistent intake, case selection, repair progress, and reminder scheduling."""
import json
from datetime import datetime, timedelta, timezone


class Workflow:
    def init_workflow(self):
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS intake (
                ticket_id TEXT PRIMARY KEY, answers TEXT NOT NULL, pending TEXT);
            CREATE TABLE IF NOT EXISTS workflow (
                ticket_id TEXT PRIMARY KEY, technician TEXT DEFAULT '', repair_note TEXT DEFAULT '',
                reminder_at TEXT);
        ''')

    def workflow_command(self, text, previous):
        command, _, argument = text.partition(' ')
        command = command.lower()
        if command == '/new' or text.lower() in ['new report', 'new issue', 'create new report']:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('active_case','new')")
            return {'reply': 'What is the new issue? Describe what happened and where.'}, None, argument
        if command == '/cases':
            cases = self.query('SELECT id,status,summary FROM tickets ORDER BY created_at DESC')
            return {'reply': '\n'.join(f"{t['id']} | {t['status']} | {t['summary'][:100]}" for t in cases) or 'No reports yet.'}, previous, None
        if command == '/case':
            ticket = self.ticket(argument.strip().upper())
            if not ticket:
                return {'reply': 'Case not found. Use /cases to list your reports.'}, previous, None
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('active_case',?)", (ticket['id'],))
            return {'reply': self.status_text(ticket), 'ticket_id': ticket['id']}, ticket, None
        if command in ['/resolved', '/unresolved']:
            ticket = self.ticket(argument.strip().upper()) if argument else previous
            if not ticket or ticket['status'] != 'awaiting_confirmation':
                return {'reply': 'Select a case awaiting confirmation using /case TKT-ID.'}, previous, None
            target = 'closed' if command == '/resolved' else 'in_progress'
            self.db.execute('UPDATE tickets SET status=?,updated_at=? WHERE id=?', (target, self.workflow_now(), ticket['id']))
            if target == 'closed':
                self.release_case_slot(ticket['id'])
            self.reset_reminder(ticket['id'])
            reply = f"{ticket['id']}: " + ('Thank you for confirming. Your case is closed.' if target == 'closed' else 'The issue is still unresolved. Your manager has been asked to continue the repair.')
            self.queue(ticket['id'], 'telegram', {'chat_id': self.c.manager, 'text': reply})
            return {'reply': reply, 'ticket_id': ticket['id']}, ticket, None
        return None, previous, None

    def workflow_now(self):
        return datetime.now(timezone.utc).isoformat()

    def intake_question(self, tid, assessment, text):
        if assessment['needs_human'] or assessment['urgency'] in ['high', 'crisis']:
            return ''
        rows = self.query('SELECT * FROM intake WHERE ticket_id=?', (tid,))
        answers = json.loads(rows[0]['answers']) if rows else {}
        pending = rows[0]['pending'] if rows else None
        if pending:
            if len(text.strip()) < 3 or text.lower().strip() in ['yes', 'no', 'maybe']:
                return 'Please describe the detail requested, or say "unknown" if you cannot tell.'
            answers[pending] = text
        questions = {
            'detail': self.missing_context_question({**assessment, 'question': ''}, None) or assessment['question'] or 'Where is the issue, and what exactly is happening?',
            'onset': 'When did this start, and is it constant or intermittent?',
            'impact': 'How is this affecting you? Is there any damage or safety concern?',
            'access': 'What have you already tried, and when can someone access the unit? You can attach a photo or say unknown.',
        }
        if assessment['issue_type'] == 'plumbing':
            questions['impact'] = 'Is anything electrical near the water, and is there any damage?'
        pending = next((key for key in questions if key not in answers), None)
        self.db.execute('INSERT OR REPLACE INTO intake VALUES (?,?,?)', (tid, json.dumps(answers), pending))
        return questions[pending] if pending else ''

    def release_case_slot(self, tid):
        self.db.execute("UPDATE scheduling SET state='closed',revision=revision+1 WHERE ticket_id=?", (tid,))
        self.db.execute('UPDATE inspection_slots SET booked_by=NULL WHERE booked_by=?', (tid,))

    def reset_reminder(self, tid):
        self.db.execute('INSERT OR IGNORE INTO workflow(ticket_id) VALUES (?)', (tid,))
        self.db.execute('UPDATE workflow SET reminder_at=? WHERE ticket_id=?',
                        ((datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(), tid))

    def repair_update(self, tid, actor, action, text=''):
        if str(actor) != self.c.manager:
            raise PermissionError('Only the registered manager can update repairs.')
        if not isinstance(text, str) or len(text) > 2000:
            raise ValueError('Repair details must be under 2,000 characters.')
        with self.lock, self.db:
            ticket = self.ticket(tid)
            if not ticket or ticket['status'] in ['closed', 'waiting_on_tenant']:
                raise ValueError('Select a submitted, active case.')
            targets = {'assign': 'assigned', 'progress': 'in_progress', 'complete': 'awaiting_confirmation'}
            if action not in targets or not text.strip():
                raise ValueError('Provide a technician for assignment or a repair update.')
            target = targets[action]
            stored = self.query('SELECT * FROM workflow WHERE ticket_id=?', (tid,))
            field = 'technician' if action == 'assign' else 'repair_note'
            if ticket['status'] == target and stored and stored[0][field] == text.strip():
                return {'ticket_id': tid, 'status': target}
            if action == 'progress' and ticket['status'] not in ['assigned', 'in_progress']:
                raise ValueError('Assign a technician before recording repair progress.')
            self.reset_reminder(tid)
            if action == 'assign':
                self.db.execute('UPDATE workflow SET technician=? WHERE ticket_id=?', (text.strip(), tid))
                self.update_details(tid, text.strip()[:80], 'Coordinate inspection and repair')
            else:
                self.db.execute('UPDATE workflow SET repair_note=? WHERE ticket_id=?', (text.strip(), tid))
            self.db.execute('UPDATE tickets SET status=?,updated_at=? WHERE id=?', (target, self.workflow_now(), tid))
            message = f"{tid}: {target.replace('_', ' ')}. {text.strip()}"
            if action == 'complete':
                self.release_case_slot(tid)
                message += f' Has the issue been resolved? Reply /resolved {tid} or /unresolved {tid}.'
            self.db.execute('INSERT INTO messages(ticket_id,role,text,created_at) VALUES (?,?,?,?)', (tid, 'manager', message, self.workflow_now()))
            self.reply(tid, message)
        self.dispatch()
        return {'ticket_id': tid, 'status': target}

    def reminders(self, at=None):
        stamp = at or datetime.now(timezone.utc)
        with self.lock, self.db:
            for ticket in self.query("SELECT * FROM tickets WHERE status NOT IN ('closed','waiting_on_tenant')"):
                tid = ticket['id']
                rows = self.query('SELECT reminder_at FROM workflow WHERE ticket_id=?', (tid,))
                due = rows[0]['reminder_at'] if rows and rows[0]['reminder_at'] else ticket['due_at']
                if datetime.fromisoformat(due) > stamp:
                    continue
                message = f"{tid}: Still {ticket['status'].replace('_', ' ')}. "
                if ticket['status'] == 'awaiting_confirmation':
                    self.reply(tid, message + f'Please confirm /resolved {tid} or /unresolved {tid}.')
                else:
                    self.queue(tid, 'telegram', {'chat_id': self.c.manager, 'text': message + 'Please acknowledge or provide a repair update.'})
                    self.reply(tid, message + 'We have reminded your property manager to provide an update.')
                self.db.execute('INSERT OR IGNORE INTO workflow(ticket_id) VALUES (?)', (tid,))
                delay = 2 if ticket['urgency'] in ['high', 'crisis'] else 24
                self.db.execute('UPDATE workflow SET reminder_at=? WHERE ticket_id=?', ((stamp + timedelta(hours=delay)).isoformat(), tid))
        self.dispatch()
