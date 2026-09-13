"""Approval-gated local inspection calendar. Never implies external contractor dispatch."""
import json
from datetime import datetime, timedelta, timezone

MYT = timezone(timedelta(hours=8))


class Scheduling:
    def init_scheduling(self):
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS inspection_slots (
                id TEXT PRIMARY KEY, technician TEXT, starts_at TEXT, ends_at TEXT,
                issue_type TEXT, booked_by TEXT);
            CREATE TABLE IF NOT EXISTS scheduling (
                ticket_id TEXT PRIMARY KEY, state TEXT, offered TEXT DEFAULT '[]',
                rejected TEXT DEFAULT '[]', selected TEXT, revision INTEGER DEFAULT 0);
        ''')
        # Seed once; restarting must never replenish slots or forget reservations.
        if not self.query("SELECT value FROM meta WHERE key='calendar_seeded'"):
            base = datetime.now(MYT).replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
            with self.db:
                for day in range(3):
                    for hour in [10, 14, 16]:
                        start = base.replace(hour=hour) + timedelta(days=day)
                        self.db.execute('INSERT INTO inspection_slots VALUES (?,?,?,?,?,NULL)',
                            (f'AC{day}{hour}', 'Demo AC technician', start.isoformat(),
                             (start + timedelta(hours=1)).isoformat(), 'hvac'))
                self.db.execute("INSERT INTO meta VALUES ('calendar_seeded','1')")

    def schedule(self, tid):
        rows = self.query('SELECT * FROM scheduling WHERE ticket_id=?', (tid,))
        return rows[0] if rows else None

    def slot_label(self, sid):
        slot = self.query('SELECT * FROM inspection_slots WHERE id=?', (sid,))[0]
        return datetime.fromisoformat(slot['starts_at']).astimezone(MYT).strftime('%a %d %b, %I:%M %p MYT') + ' — ' + slot['technician']

    def schedule_reply(self, tid, text, buttons=None):
        self.reply(tid, text)
        if buttons:
            row = self.query("SELECT id,payload FROM actions WHERE ticket_id=? AND kind='telegram' ORDER BY rowid DESC LIMIT 1", (tid,))[0]
            payload = json.loads(row['payload'])
            payload['keyboard'] = buttons
            self.db.execute('UPDATE actions SET payload=? WHERE id=?', (json.dumps(payload), row['id']))

    def offer_slots(self, tid, allowed=None):
        current = self.schedule(tid)
        if not current:
            self.db.execute("INSERT INTO scheduling(ticket_id,state) VALUES (?,'offering')", (tid,))
            current = self.schedule(tid)
        rejected = json.loads(current['rejected'])
        slots = [s for s in self.query("SELECT * FROM inspection_slots WHERE booked_by IS NULL AND issue_type='hvac' ORDER BY starts_at")
                 if s['id'] not in rejected and (allowed is None or s['id'] in allowed) and datetime.fromisoformat(s['starts_at']) > datetime.now(MYT)][:2]
        revision = current['revision'] + 1
        self.db.execute('UPDATE scheduling SET state=?,offered=?,selected=NULL,revision=? WHERE ticket_id=?',
            ('offering' if slots else 'needs_manager', json.dumps([s['id'] for s in slots]), revision, tid))
        if not slots:
            self.schedule_reply(tid, 'No further local inspection slots are available. Your manager needs to arrange another option; no appointment is booked.')
            self.queue(tid, 'telegram', {'chat_id': self.c.manager, 'text': tid + ': Inspection slots exhausted. Please coordinate availability with the tenant.'})
            return
        buttons = [[{'text': self.slot_label(s['id']), 'callback_data': f"pick:{tid}:{revision}:{s['id']}"}] for s in slots]
        buttons.append([{'text': 'Neither works — show alternatives', 'callback_data': f'other:{tid}:{revision}'}])
        self.schedule_reply(tid, 'Choose a local inspection slot (seeded demo calendar; no contractor will be dispatched). Manager approval is required.\n' +
            '\n'.join(f"{i+1}. {self.slot_label(s['id'])}" for i, s in enumerate(slots)) +
            '\nTap a slot, reply 1 or 2, or reply “another time”.', buttons)

    def scheduling_action(self, tid, actor, action, revision, slot=None):
        with self.lock:
            manager_action = action in ['approve', 'decline']
            if str(actor) != (self.c.manager if manager_action else self.c.tenant):
                raise PermissionError('Only the registered ' + ('manager' if manager_action else 'tenant') + ' can take this action.')
            current, ticket = self.schedule(tid), self.ticket(tid)
            if not current or not ticket or ticket['status'] == 'closed':
                raise ValueError('This case is not available for scheduling.')
            if current['revision'] != int(revision):
                raise ValueError('That offer has changed. Use the latest message or /slots.')
            with self.db:
                if action in ['pick', 'other']:
                    if current['state'] != 'offering':
                        raise ValueError('This offer is no longer open. Use /status.')
                    offered = json.loads(current['offered'])
                    if action == 'other':
                        self.db.execute('UPDATE scheduling SET rejected=? WHERE ticket_id=?',
                            (json.dumps(json.loads(current['rejected']) + offered), tid))
                        self.offer_slots(tid)
                    else:
                        if slot not in offered:
                            raise ValueError('Choose one of the offered slots.')
                        self.db.execute("UPDATE scheduling SET selected=?,state='awaiting_approval' WHERE ticket_id=?", (slot, tid))
                        self.schedule_reply(tid, 'You selected ' + self.slot_label(slot) + '. Awaiting manager approval; no booking yet.')
                        self.queue(tid, 'telegram', {'chat_id': self.c.manager,
                            'text': tid + ': Tenant selected ' + self.slot_label(slot) + '. Approve this local demo reservation? No contractor is dispatched and no spending is authorized.',
                            'keyboard': [[{'text': 'Approve reservation', 'callback_data': f'approve:{tid}:{revision}'},
                                          {'text': 'Decline / offer alternatives', 'callback_data': f'decline:{tid}:{revision}'}]]})
                elif action in ['approve', 'decline']:
                    if current['state'] == 'booked' and action == 'approve':
                        return {'state': 'booked'}
                    if current['state'] != 'awaiting_approval':
                        raise ValueError('No reservation is awaiting approval.')
                    sid = current['selected']
                    if action == 'decline':
                        self.db.execute('UPDATE scheduling SET rejected=? WHERE ticket_id=?',
                            (json.dumps(json.loads(current['rejected']) + [sid]), tid))
                        self.schedule_reply(tid, 'Your manager declined that slot. I will check alternatives.')
                        self.offer_slots(tid)
                    else:
                        selected = self.query('SELECT * FROM inspection_slots WHERE id=?', (sid,))[0]
                        future = datetime.fromisoformat(selected['starts_at']) > datetime.now(MYT)
                        changed = self.db.execute('UPDATE inspection_slots SET booked_by=? WHERE id=? AND booked_by IS NULL', (tid, sid)).rowcount if future else 0
                        if not changed:
                            self.schedule_reply(tid, 'That slot is no longer available. Nothing was booked; I will offer alternatives.')
                            self.db.execute('UPDATE scheduling SET rejected=? WHERE ticket_id=?',
                                (json.dumps(json.loads(current['rejected']) + [sid]), tid))
                            self.offer_slots(tid)
                        else:
                            self.db.execute("UPDATE scheduling SET state='booked' WHERE ticket_id=?", (tid,))
                            self.queue(tid, 'assessment', {'text': 'Manager approved local calendar reservation: ' + self.slot_label(sid)})
                            self.schedule_reply(tid, 'Local inspection reservation confirmed: ' + self.slot_label(sid) +
                                '. This is a demo calendar booking; your manager must arrange the real technician. No external calendar event was created.')
                            self.queue(tid, 'telegram', {'chat_id': self.c.manager, 'text': tid + ': Local reservation saved for ' + self.slot_label(sid) + '. Arrange the real contractor separately.'})
                else:
                    raise ValueError('Unknown scheduling action')
            self.dispatch()
            return {'state': self.schedule(tid)['state']}

    def scheduling_text(self, ticket, text):
        current = self.schedule(ticket['id'])
        low = text.lower().strip()
        if low in ['/start', '/help', '/status', 'status', 'any update?', 'any update']:
            return False
        if low == '/slots':
            with self.db:
                if ticket['issue_type'] != 'hvac' or ticket['urgency'] in ['high', 'crisis'] or ticket['needs_human']:
                    self.reply(ticket['id'], 'This case needs manager coordination before scheduling.')
                elif current and current['state'] in ['booked', 'awaiting_approval']:
                    self.reply(ticket['id'], self.scheduling_status(ticket['id']))
                else:
                    self.offer_slots(ticket['id'])
            return True
        if current and current['state'] == 'offering':
            if low in ['another time', 'neither', 'neither works', 'other', 'none', 'none of these']:
                self.scheduling_action(ticket['id'], self.c.tenant, 'other', current['revision'])
                return True
            if low in ['1', '2']:
                offered = json.loads(current['offered'])
                index = int(low) - 1
                if index < len(offered):
                    self.scheduling_action(ticket['id'], self.c.tenant, 'pick', current['revision'], offered[index])
                    return True
            # New danger reports always go through triage rather than calendar interpretation.
            if any(word in low for word in ['smoke', 'spark', 'fire', 'gas', 'leak', 'water', 'worse']):
                return False
            candidates = [s for s in self.query('SELECT id,technician,starts_at FROM inspection_slots WHERE booked_by IS NULL')
                          if s['id'] not in json.loads(current['rejected']) and datetime.fromisoformat(s['starts_at']) > datetime.now(MYT)]
            try:
                intent = self.adapter.scheduling_intent(text, candidates, json.loads(current['offered']))
            except Exception:
                with self.db:
                    self.reply(ticket['id'], 'I could not interpret that availability. Please tap a slot, reply 1 or 2, or reply “another time”. No booking was made.')
                return True
            if intent['intent'] == 'reject':
                self.scheduling_action(ticket['id'], self.c.tenant, 'other', current['revision'])
                return True
            if intent['intent'] == 'select' and len(intent['slots']) == 1 and intent['slots'][0] in json.loads(current['offered']):
                self.scheduling_action(ticket['id'], self.c.tenant, 'pick', current['revision'], intent['slots'][0])
                return True
            if intent['intent'] == 'availability':
                with self.db:
                    self.offer_slots(ticket['id'], allowed=intent['slots'])
                return True
        return False

    def scheduling_status(self, tid):
        s = self.schedule(tid)
        if not s:
            return ''
        return ' Inspection: ' + s['state'].replace('_', ' ') + ('. ' + self.slot_label(s['selected']) if s['selected'] else '') + '. Local demo calendar only.'
