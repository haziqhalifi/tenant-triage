"""Launch a fresh, isolated recording rehearsal. Never connects to live providers."""
import argparse
import tempfile
from http.server import ThreadingHTTPServer
from config import Config, ROOT
from engine import Engine
from app import handler_for


LEAK = [
    '/new My bathroom sink is leaking',
    'Under the bathroom sink. A bucket is containing the drips.',
    'It started this morning and drips continuously.',
    'No electrics near the bucket and no damage yet.',
    'I put a bucket underneath. Someone can access the unit tomorrow afternoon.',
]
AC = [
    '/new My AC is not cold',
    'The bedroom AC blows air but does not cool.',
    'Since yesterday evening, whenever it is switched on.',
    'The bedroom is hot. No unusual smell or visible damage.',
    'I cleaned the filter. I can be home tomorrow for inspection.',
]
WORSENING = 'The leak is getting worse and water is spreading near the socket.'


def prepare(engine):
    if not engine.c.demo:
        raise ValueError('Recording preparation requires demo mode.')
    tickets = []
    for prefix, messages in [('leak', LEAK), ('ac', AC)]:
        for i, message in enumerate(messages):
            result = engine.receive(f'recording:{prefix}:{i}', engine.c.tenant, message)
        tickets.append(result['ticket_id'])
    leak, ac = tickets
    engine.update_details(leak, 'Property manager', 'Inspect sink connection and arrange repair; awaiting manager review.')
    engine.update_details(ac, 'Maintenance coordinator', 'Tenant to choose an inspection slot; manager approval required.')
    engine.receive('recording:select-leak', engine.c.tenant, '/case ' + leak)
    return {'leak': leak, 'ac': ac}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8098)
    args = parser.parse_args()
    folder = ROOT / 'data'
    folder.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='recording-', suffix='.sqlite3', dir=folder, delete=False) as file:
        path = file.name
    engine = Engine(Config(demo=True, db=path))
    ids = prepare(engine)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(engine))
    print(f'UnitCue recording demo: http://127.0.0.1:{args.port}', flush=True)
    print(f"Leak: {ids['leak']} | AC: {ids['ac']} | Database: {path}", flush=True)
    print('Simulated notifications and model assessment. Fresh run; existing demo/live data preserved.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        engine.db.close()


if __name__ == '__main__':
    main()
