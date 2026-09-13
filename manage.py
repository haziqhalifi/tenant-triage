"""Local operator tool. Stop app.py before running this command."""
import argparse
from config import Config
from engine import Engine

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('command', choices=['actions', 'retry'])
parser.add_argument('action_id', nargs='?')
args = parser.parse_args()
config = Config()
config.validate()
engine = Engine(config)
if args.command == 'actions':
    for action in engine.snapshot()['actions']:
        print(action['id'], action['kind'], action['status'], action['ticket_id'])
else:
    if not args.action_id:
        parser.error('retry requires ACTION_UUID; check the recipient before retrying uncertain delivery')
    engine.dispatch(args.action_id)
    found = [a for a in engine.snapshot()['actions'] if a['id'] == args.action_id]
    if not found:
        parser.error('Action not found')
    print(found[0]['status'])
engine.db.close()
