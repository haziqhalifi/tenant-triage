"""Local manager workspace metadata; notes never send external messages."""
from datetime import datetime, timezone


class Dashboard:
    def init_dashboard(self):
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS case_details (
                ticket_id TEXT PRIMARY KEY, owner TEXT DEFAULT 'Property manager', next_step TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS case_notes (
                id INTEGER PRIMARY KEY, ticket_id TEXT, text TEXT, created_at TEXT);
        ''')

    def update_details(self, tid, owner, next_step):
        if not isinstance(owner,str) or not owner.strip() or len(owner)>80:
            raise ValueError('Owner must be 1–80 characters.')
        if not isinstance(next_step,str) or len(next_step)>500:
            raise ValueError('Next step must be under 500 characters.')
        with self.lock, self.db:
            if not self.ticket(tid):
                raise ValueError('Case not found')
            self.db.execute('INSERT OR REPLACE INTO case_details VALUES (?,?,?)',(tid,owner.strip(),next_step.strip()))
        return {'ok':True}

    def add_note(self, tid, text):
        if not isinstance(text,str) or not text.strip() or len(text)>2000:
            raise ValueError('Note must be 1–2,000 characters.')
        with self.lock, self.db:
            if not self.ticket(tid):
                raise ValueError('Case not found')
            self.db.execute('INSERT INTO case_notes(ticket_id,text,created_at) VALUES (?,?,?)',
                            (tid,text.strip(),datetime.now(timezone.utc).isoformat()))
        return {'ok':True}
