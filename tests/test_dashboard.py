import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from config import Config
from engine import Engine
from app import handler_for


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'data').mkdir()
        c=Config(demo=True,db=str(self.root/'test.db'))
        self.e=Engine(c)
        self.tid=self.e.receive('initial',c.tenant,'AC not cold')['ticket_id']
        self.e.receive('context',c.tenant,'Bedroom. It is blowing air but not cooling.')
        for i, text in enumerate(['Since yesterday, constant.', 'Room is hot, no damage.', 'Filter cleaned. Available tomorrow.']):
            self.e.receive('intake'+str(i), c.tenant, text)
        c.demo=False
        self.sender=patch.object(self.e.adapter,'send',return_value={})
        self.sender.start()
        with patch('app.ROOT',self.root):
            handler=handler_for(self.e)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        with urllib.request.urlopen(self.base+'/api/state') as response:
            self.csrf=json.load(response)['csrf']
        self.cookie=''

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.sender.stop()
        self.e.db.close()
        self.tmp.cleanup()

    def post(self,path,body,csrf=True):
        headers={'Content-Type':'application/json','Cookie':self.cookie}
        if csrf: headers['X-CSRF-Token']=self.csrf
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode(),headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                if r.headers.get('Set-Cookie'): self.cookie=r.headers['Set-Cookie'].split(';')[0]
                return r.status,json.load(r)
        except urllib.error.HTTPError as e:
            with e:
                return e.code,json.load(e)

    def login(self):
        return self.post('/api/login',{'password':(self.root/'data/manager-access.txt').read_text()})

    def test_locked_mutations_and_csrf_rejected(self):
        self.assertEqual(self.post('/api/ack',{'ticket_id':self.tid})[0],403)
        self.assertEqual(self.post('/api/login',{'password':'anything'},csrf=False)[0],403)
        self.assertEqual(self.e.ticket(self.tid)['status'],'open')

    def test_login_notes_details_and_logout(self):
        self.assertEqual(self.login()[0],200)
        before=len(self.e.snapshot()['actions'])
        self.assertEqual(self.post('/api/note',{'ticket_id':self.tid,'text':'Internal coordination note'})[0],200)
        self.assertEqual(self.post('/api/details',{'ticket_id':self.tid,'owner':'Maintenance team','next_step':'Arrange inspection'})[0],200)
        self.assertEqual(len(self.e.snapshot()['actions']),before)
        self.assertEqual(self.e.snapshot()['notes'][0]['text'],'Internal coordination note')
        self.assertEqual(self.post('/api/logout',{})[0],200)
        self.assertEqual(self.post('/api/ack',{'ticket_id':self.tid})[0],403)

    def test_unlocked_manager_cannot_impersonate_tenant(self):
        self.login()
        self.assertEqual(self.post('/api/message',{'text':'Fake report'})[0],403)
        self.assertEqual(self.post('/api/schedule',{'action':'pick'})[0],403)
        self.assertEqual(self.post('/api/fail-email',{})[0],403)
        self.assertEqual(self.post('/api/ack',{'ticket_id':self.tid})[0],200)
        self.assertEqual(self.e.ticket(self.tid)['status'],'acknowledged')

    def test_validation_and_wrong_password(self):
        self.assertEqual(self.post('/api/login',{'password':'wrong'})[0],401)
        self.login()
        self.assertEqual(self.post('/api/note',{'ticket_id':self.tid,'text':''})[0],400)
        self.assertEqual(self.post('/api/details',{'ticket_id':'missing','owner':'Team','next_step':''})[0],400)
        self.assertEqual(self.post('/api/retry',{'action_id':None})[0],400)
