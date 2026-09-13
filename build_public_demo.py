"""Build a credentials-free static showcase from fresh fictional fixtures."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import config
import seed_demo
from engine import Engine
import shutil

root=Path(__file__).resolve().parent
out=root/'public-demo'
out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    temp=Path(directory)
    (temp/'data').mkdir()
    with patch.dict('os.environ',{},clear=True), patch('config.load_env'), patch('seed_demo.ROOT',temp):
        seed_demo.seed()
        engine=Engine(config.Config(demo=True,db=str(temp/'data/demo.sqlite3')))
        snapshot=engine.snapshot()
        engine.db.close()
snapshot.update(unlocked=True,csrf='public-demo',services={'telegram':'simulated','model':'simulated','email':'simulated','calendar':'Local demo calendar'})
(out/'demo-state.json').write_text(json.dumps(snapshot))
for name in ['index.html','app.js','style.css']:
    shutil.copyfile(root/'static'/name,out/name)
shutil.copytree(root/'static/demo-photos',out/'demo-photos',dirs_exist_ok=True)
shutil.copyfile(root/'web-demo/demo-runtime.js',out/'demo-runtime.js')
index=(out/'index.html').read_text().replace('<script src="/app.js"></script>','<script src="/demo-runtime.js"></script><script src="/app.js"></script>')
(out/'index.html').write_text(index)
js=(out/'app.js').read_text().replace('Demo mode: model decisions and outgoing notifications are simulated. Use Rehearsal to test a workflow.', '')
js=js.replace('Edit .env locally and restart the app to change integrations.', 'This showcase has no live service connections or credentials.')
js=js.replace('The local key is in data/manager-access.txt. Sessions expire after eight hours or a server restart.', 'Demo controls are unlocked. Changes are saved only in this browser; no manager key is required.')
js=js.replace('This workspace runs on this computer only.', 'This public demo stores changes in your browser only.')
js=js.replace('function access(){', "function access(){if(state.mode==='demo'){toast('Public demo controls are already unlocked.');return;}")
(out/'app.js').write_text(js)
(out/'vercel.json').write_text(json.dumps({'framework':None,'buildCommand':None,'outputDirectory':'.','headers':[{'source':'/(.*)','headers':[{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'Content-Security-Policy','value':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; connect-src 'self'"}]}]}))
(out/'.vercelignore').write_text('.env*\n.vercel\n.git\n.gitignore\n*.sqlite3\nmanager-access.txt\n')
print('Built public-demo with fictional fixtures only.')
