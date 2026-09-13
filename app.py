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
    if chat == engine.c.manager and text.startswith('/close '):
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


def handler_for(engine):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
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
            if self.path == '/api/state':
                return self.respond(200, {**engine.snapshot(), 'csrf': token})
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path not in files:
                return self.respond(404, {'error': 'Not found'})
            name, mime = files[self.path]
            self.respond(200, (ROOT / 'static' / name).read_bytes(), mime)

        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-CSRF-Token') != token:
                return self.respond(403, {'error': 'Refresh the local console before trying again.'})
            # Console mutations are demo-only; live authority is tied to Telegram user IDs.
            if not engine.c.demo:
                return self.respond(403, {'error': 'Use the registered Telegram chats for live actions.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 10000:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected an object')
                if self.path == '/api/message':
                    if not isinstance(data.get('text'), str):
                        raise ValueError('Message text is required')
                    result = engine.receive('demo:' + str(data.get('id') or uuid.uuid4()), engine.c.tenant, data['text'])
                elif self.path in ['/api/ack', '/api/close']:
                    result = engine.acknowledge(data.get('ticket_id'), engine.c.manager, close=self.path == '/api/close')
                elif self.path == '/api/retry':
                    engine.dispatch(data.get('action_id'))
                    result = {'ok': True}
                elif self.path == '/api/fail-email':
                    engine.adapter.fail_next_email = True
                    result = {'ok': True}
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
    port = int(os.getenv('PORT', '8080'))
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(engine))
    print(f'TenantTriage running at http://127.0.0.1:{port} ({"DEMO — simulated actions" if config.demo else "LIVE"})', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
