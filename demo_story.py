"""Enrich existing fictional showcase cases for the video; no external sends."""
from datetime import datetime, timedelta, timezone
from config import Config, ROOT
from engine import Engine


STORIES = {
    'DEMO-0001': [
        ('tenant', 'There is a damp patch on my bathroom ceiling. Here is a photo.'),
        ('agent', 'DEMO-0001: Unit A-08-02 is registered. Is it dripping now, and is the water contained?'),
        ('tenant', 'It is dripping slowly into a bucket. It started this morning.'),
        ('agent', 'Is anything electrical near the water? Is there damage, and when can maintenance access the unit?'),
        ('tenant', 'No electrics nearby. The paint is peeling. I am home this afternoon.'),
        ('agent', 'DEMO-0001: Report submitted for manager review. Priority: medium. Response target: 48 hours. Your conversation and photo are attached to this case.'),
        ('tenant', 'The leak is getting worse. Water is spreading across the ceiling and onto the floor.'),
        ('agent', 'DEMO-0001 updated. Priority raised to high. The manager has been alerted in this simulated demo. Response target: 2 hours; this is not a guaranteed repair time.'),
        ('tenant', 'Any update?'),
        ('agent', 'DEMO-0001: Open, high priority. Manager Telegram notification: simulated. No manager acknowledgement recorded yet. Next step: inspect the unit above and coordinate building maintenance.'),
    ],
    'DEMO-0003': [
        ('tenant', 'My AC is not cold.'),
        ('agent', 'Which room is affected, and is the AC blowing air but not cooling?'),
        ('tenant', 'The bedroom. It blows warm air even at the lowest temperature.'),
        ('agent', 'When did this start, and have you noticed damage or an unusual smell?'),
        ('tenant', 'Yesterday evening. No unusual smell or visible damage.'),
        ('agent', 'What have you tried, and when can someone access the unit?'),
        ('tenant', 'I cleaned the filter. I can be home tomorrow for inspection.'),
        ('agent', 'DEMO-0003: Routine AC report submitted. Priority: medium. Response target: 48 hours. Choose a local inspection slot; manager approval is required before reservation.'),
    ],
}


def enrich(engine):
    if not engine.c.demo:
        raise ValueError('Fictional story data requires demo mode.')
    added = []
    with engine.lock, engine.db:
        for tid, story in STORIES.items():
            marker = 'video-story-v1:' + tid
            ticket = engine.ticket(tid)
            if not ticket or engine.query('SELECT value FROM meta WHERE key=?', (marker,)):
                continue
            # Preserve edited conversations; only expand the original two-message fixture.
            messages = engine.query('SELECT * FROM messages WHERE ticket_id=? ORDER BY id', (tid,))
            if len(messages) != 2 or messages[0]['text'] != ticket['summary'] or not messages[1]['text'].startswith(tid + ': Report saved for unit '):
                continue
            for original, (role, text) in zip(messages, story[:2]):
                engine.db.execute('UPDATE messages SET text=? WHERE id=?', (text, original['id']))
            stamp = datetime.now(timezone.utc)
            for i, (role, text) in enumerate(story[2:]):
                engine.db.execute('INSERT INTO messages(ticket_id,role,text,created_at) VALUES (?,?,?,?)',
                    (tid, role, text, (stamp - timedelta(minutes=len(story)-i)).isoformat()))
            if tid == 'DEMO-0003':
                schedule = engine.schedule(tid)
                if schedule and schedule['selected']:
                    slot = engine.slot_label(schedule['selected'])
                    for role, text in [('agent', 'Available local inspection option: ' + slot),
                                       ('tenant', 'That time works for me.'),
                                       ('agent', 'You selected ' + slot + '. Awaiting manager approval; no booking yet.')]:
                        engine.db.execute('INSERT INTO messages(ticket_id,role,text,created_at) VALUES (?,?,?,?)', (tid, role, text, stamp.isoformat()))
            engine.db.execute('INSERT INTO meta VALUES (?,?)', (marker, '1'))
            added.append(tid)
    return added


if __name__ == '__main__':
    engine = Engine(Config(demo=True, db=str(ROOT / 'data' / 'demo.sqlite3')))
    try:
        print('Expanded existing dummy cases:', ', '.join(enrich(engine)) or 'Already prepared or edited; preserved.')
        print('No real messages sent. Existing dashboard and cases retained.')
    finally:
        engine.db.close()
