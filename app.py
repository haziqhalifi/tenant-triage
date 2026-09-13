"""Run with python3 app.py. No third-party packages required."""
import json
import os
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from config import Config, ROOT
from engine import Engine


def process_update(engine, update):
    callback = update.get('callback_query')
    if callback:
        message = 'Action unavailable'
        try:
            sender = str(callback['from']['id'])
            data = callback.get('data', '')
            if data.split(':')[0] in ['pick', 'other', 'approve', 'decline']:
                parts = data.split(':')
                if len(parts) not in [3, 4]:
                    raise ValueError('Invalid scheduling action')
                result = engine.scheduling_action(parts[1], sender, parts[0], int(parts[2]), parts[3] if len(parts) == 4 else None)
                message = result['state'].replace('_', ' ')
            if data.startswith('ack:'):
                engine.acknowledge(data[4:], sender)
                message = 'Case acknowledged'
        except (ValueError, PermissionError) as exc:
            message = str(exc)
        engine.adapter.telegram('answerCallbackQuery', {'callback_query_id': callback['id'], 'text': message})
        return
    message = update.get('message', {})
    if message.get('chat', {}).get('type') != 'private':
        return
    chat = str(message['chat']['id'])
    text = message.get('text', message.get('caption', ''))
    if chat == engine.c.manager and text.split(' ')[0] in ['/assign', '/progress', '/complete']:
        parts = text.split(maxsplit=2)
        try:
            if len(parts) != 3:
                raise ValueError('Use /assign TKT-ID technician, /progress TKT-ID update, or /complete TKT-ID repair details.')
            engine.repair_update(parts[1].upper(), chat, parts[0][1:], parts[2])
        except (ValueError, PermissionError) as exc:
            engine.adapter.telegram('sendMessage', {'chat_id': chat, 'text': str(exc)})
    elif chat == engine.c.manager and text.startswith('/close '):
        try:
            engine.acknowledge(text.split(maxsplit=1)[1].strip(), chat, close=True)
        except ValueError:
            pass
    elif chat == engine.c.tenant and (text or message.get('photo')):
        photos = message.get('photo', [])
        # Telegram text can exceed the console limit; reject it without blocking the polling offset.
        if len(text.strip()) > 4000:
            engine.adapter.telegram('sendMessage', {'chat_id': chat, 'text': 'Please split your report into messages under 4,000 characters.'})
            return
        engine.receive('telegram:' + str(update['update_id']), chat, text, photos[-1]['file_id'] if photos else None)


def poll(engine):
    while True:
        try:
            with engine.lock:
                rows = engine.query("SELECT value FROM meta WHERE key='offset'")
                offset = int(rows[0]['value']) if rows else 0
            updates = engine.adapter.telegram('getUpdates', {'offset': offset, 'timeout': 25, 'allowed_updates': ['message', 'callback_query']})
            for update in updates:
                process_update(engine, update)
                with engine.lock, engine.db:
                    engine.db.execute("INSERT OR REPLACE INTO meta VALUES ('offset',?)", (str(update['update_id'] + 1),))
        except Exception as exc:
            print('Telegram polling interrupted:', type(exc).__name__, '(retrying)', flush=True)
            time.sleep(3)


def reminder_worker(engine):
    while True:
        try:
            engine.reminders()
        except Exception as exc:
            print('Reminder check interrupted:', type(exc).__name__, flush=True)
        time.sleep(60)


def handler_for(engine):
    token = secrets.token_urlsafe(32)
    sessions = {}
    failures = []
    password_file = ROOT / 'data' / 'manager-access.txt'
    if not password_file.exists():
        password_file.write_text(secrets.token_urlsafe(24))
        password_file.chmod(0o600)
    password = password_file.read_text().strip()

    class Handler(BaseHTTPRequestHandler):
        def unlocked(self):
            from http.cookies import SimpleCookie
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
                value = cookie.get('manager_session')
                return bool(value and sessions.get(value.value, 0) > time.time())
            except Exception:
                return False

        def log_message(self, *_):
            pass

        def respond(self, status, value, content_type='application/json'):
            body = json.dumps(value).encode() if content_type == 'application/json' else value
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host') in [f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}']

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403, {'error': 'Local access only'})
            if self.path == '/narration.m4a':
                audio = ROOT / 'data' / 'narration.m4a'
                if not engine.c.demo or not audio.exists():
                    return self.respond(404, {'error': 'Narration unavailable'})
                return self.respond(200, audio.read_bytes(), 'audio/mp4')
            if self.path == '/api/state':
                return self.respond(200, {**engine.snapshot(), 'csrf': token, 'unlocked': self.unlocked() or engine.c.demo})
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            for photo in ['ceiling-leak', 'damaged-socket', 'dripping-ac']:
                files['/demo-photos/'+photo+'.jpg'] = ('demo-photos/'+photo+'.jpg', 'image/jpeg')
            files['/narration.js'] = ('narration.js', 'text/javascript; charset=utf-8')
            if self.path.startswith('/?narration='):
                self.path = '/'
            if self.path not in files:
                return self.respond(404, {'error': 'Not found'})
            name, mime = files[self.path]
            self.respond(200, (ROOT / 'static' / name).read_bytes(), mime)

        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-CSRF-Token') != token:
                return self.respond(403, {'error': 'Refresh the local console before trying again.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 10000:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected an object')
                if self.path == '/api/login':
                    failures[:] = [t for t in failures if time.time()-t < 60]
                    if len(failures) >= 5:
                        return self.respond(429, {'error':'Too many attempts. Wait one minute.'})
                    if not isinstance(data.get('password'),str) or not secrets.compare_digest(data['password'], password):
                        failures.append(time.time())
                        return self.respond(401, {'error':'Incorrect manager access key.'})
                    sid = secrets.token_urlsafe(32)
                    sessions[sid] = time.time() + 8*3600
                    self.send_response(200)
                    self.send_header('Set-Cookie', f'manager_session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
                    self.send_header('Content-Type','application/json')
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                    return
                if self.path == '/api/logout':
                    from http.cookies import SimpleCookie
                    cookie=SimpleCookie(self.headers.get('Cookie',''))
                    if cookie.get('manager_session'):
                        sessions.pop(cookie['manager_session'].value,None)
                    return self.respond(200, {'ok':True})
                if not engine.c.demo and not self.unlocked():
                    return self.respond(403, {'error':'Unlock manager controls to make changes.'})
                if not engine.c.demo and (self.path in ['/api/message','/api/fail-email'] or self.path == '/api/schedule' and data.get('action') not in ['approve','decline']):
                    return self.respond(403, {'error':'Tenant actions must come from the registered Telegram account.'})
                if self.path == '/api/message':
                    if not isinstance(data.get('text'), str):
                        raise ValueError('Message text is required')
                    result = engine.receive('demo:' + str(data.get('id') or uuid.uuid4()), engine.c.tenant, data['text'])
                elif self.path in ['/api/ack', '/api/close']:
                    result = engine.acknowledge(data.get('ticket_id'), engine.c.manager, close=self.path == '/api/close')
                elif self.path == '/api/retry':
                    if not isinstance(data.get('action_id'),str) or not engine.query('SELECT id FROM actions WHERE id=?',(data['action_id'],)):
                        raise ValueError('Action not found')
                    engine.dispatch(data.get('action_id'))
                    result = {'ok': True}
                elif self.path == '/api/schedule':
                    action = data.get('action')
                    result = engine.scheduling_action(data.get('ticket_id'), engine.c.manager if action in ['approve', 'decline'] else engine.c.tenant,
                        action, data.get('revision'), data.get('slot'))
                elif self.path == '/api/fail-email':
                    engine.adapter.fail_next_email = True
                    result = {'ok': True}
                elif self.path == '/api/details':
                    result = engine.update_details(data.get('ticket_id'),data.get('owner'),data.get('next_step'))
                elif self.path == '/api/repair':
                    result = engine.repair_update(data.get('ticket_id'), engine.c.manager, data.get('action'), data.get('text', ''))
                elif self.path == '/api/note':
                    result = engine.add_note(data.get('ticket_id'),data.get('text'))
                else:
                    return self.respond(404, {'error': 'Not found'})
                self.respond(200, result)
            except (ValueError, TypeError, PermissionError) as exc:
                self.respond(400, {'error': str(exc)})
            except Exception:
                self.respond(500, {'error': 'Request failed. Your saved cases are retained; refresh to check before retrying.'})
    return Handler


def main():
    config = Config()
    config.validate()
    Path(config.db).parent.mkdir(parents=True, exist_ok=True)
    engine = Engine(config)
    engine.recover()
    if not config.demo:
        threading.Thread(target=poll, args=(engine,), daemon=True).start()
        threading.Thread(target=reminder_worker, args=(engine,), daemon=True).start()
    port = int(os.getenv('PORT', '8080'))
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(engine))
    print(f'UnitCue running at http://127.0.0.1:{port} ({"DEMO — simulated actions" if config.demo else "LIVE"})', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
