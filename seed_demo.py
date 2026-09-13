"""Add fictional dashboard fixtures to demo.sqlite3 only; never sends notifications.
Run: python3 seed_demo.py. Re-running preserves edits and does not duplicate records.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from config import Config, ROOT
from engine import Engine


def seed():
    config = Config(demo=True, db=str(ROOT / 'data' / 'demo.sqlite3'))
    engine = Engine(config)
    stamp = datetime.now(timezone.utc)
    at = lambda hours: (stamp + timedelta(hours=hours)).isoformat()
    rows = [
        ('A-08-02','plumbing','high','open', 'Water leaking through the bathroom ceiling; the wet patch is spreading.', 'Farah · Property manager','Contact building maintenance and inspect the unit above.',-2),
        ('B-15-06','electrical','crisis','escalated','Tenant reports sparks from a damaged kitchen socket. Immediate human attention required.', 'Daniel · Duty manager','Coordinate urgent electrical assessment; keep tenant away from the hazard.',-1),
        ('A-03-01','hvac','medium','open','Bedroom AC is blowing warm air after the filter was cleaned.', 'Amir · Maintenance coordinator','Review the tenant’s selected inspection slot.',20),
        ('C-11-04','hvac','medium','acknowledged','Living room AC drips during extended use. Inspection reservation approved.', 'Amir · Maintenance coordinator','Confirm access instructions before the local inspection.',30),
        ('B-06-03','pest','medium','waiting_on_tenant','Ants reported around the pantry. Awaiting details on affected areas.', 'Farah · Property manager','Ask whether the issue affects other rooms.',10),
        ('A-17-05','appliance','medium','open','Washing machine stops mid-cycle and displays an error code.', 'Mei · Service desk','Collect the appliance model and contact the approved repair team.',-5),
        ('C-04-02','noise','low','acknowledged','Repeated evening drilling reported from a neighbouring unit.', 'Daniel · Duty manager','Check permitted renovation hours with building management.',18),
        ('B-20-01','lease','low','escalated','Tenant has requested clarification about the renewal process.', 'Farah · Property manager','Review the lease and respond directly; no automated legal conclusion.',42),
        ('A-09-03','plumbing','medium','closed','Bathroom tap washer replaced; tenant confirmed the dripping stopped.', 'Amir · Maintenance coordinator','Resolved and confirmed by the tenant.',-24),
        ('C-07-06','hvac','medium','open','Study AC makes a rattling sound. Tenant cannot attend the first offered slots.', 'Mei · Service desk','Offer alternative inspection availability.',22),
        ('B-02-04','appliance','low','closed','Cooker hood light replaced and operation checked.', 'Amir · Maintenance coordinator','No further action required.',-48),
        ('A-12-01','other','medium','waiting_on_tenant','Bedroom window handle is loose; tenant has not confirmed whether it closes.', 'Mei · Service desk','Confirm whether the window can be secured.',-3),
        ('C-18-02','plumbing','high','acknowledged','Balcony drain blocked after heavy rain. Manager has acknowledged the report.', 'Daniel · Duty manager','Arrange drainage inspection and monitor water accumulation.',1),
        ('B-10-05','hvac','medium','open','Main bedroom AC has weak airflow. Tenant selected an afternoon appointment.', 'Amir · Maintenance coordinator','Approve or decline the proposed local reservation.',28),
        ('A-05-04','pest','low','closed','Pest inspection completed and kitchen entry point sealed.', 'Farah · Property manager','Follow-up confirmed no new sightings.',-72),
        ('C-14-03','hvac','medium','acknowledged','AC remote receiver intermittently fails. Local inspection reserved.', 'Mei · Service desk','Prepare appliance model details for inspection.',35),
    ]
    added = 0
    with engine.db:
        for i,(unit,issue,urgency,status,summary,owner,next_step,due) in enumerate(rows,1):
            tid=f'DEMO-{i:04d}'
            if engine.ticket(tid):
                continue
            created=at(-max(4,60-i*3))
            updated=at(-i/5)
            question = ('Which rooms are affected?' if issue=='pest' else 'Can the window be closed securely?') if status=='waiting_on_tenant' else ''
            engine.db.execute('INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (tid,f'fixture-tenant-{i}',unit,issue,urgency,summary,question,status,int(status=='escalated'),at(due),created,updated))
            engine.db.execute('INSERT INTO case_details VALUES (?,?,?)',(tid,owner,next_step))
            engine.db.execute('INSERT INTO case_notes(ticket_id,text,created_at) VALUES (?,?,?)',
                (tid,'Fictional showcase case. '+next_step,updated))
            messages=[('tenant',summary,created),('agent',f'{tid}: Report saved for unit {unit}. '+(question or 'Your property manager will coordinate the next step.'),created)]
            if status in ['acknowledged','closed']:
                messages += [('manager','Report acknowledged by the property team.',updated),('agent','Your manager has acknowledged this report.',updated)]
            if status=='closed':
                messages += [('tenant','The issue is fixed now, thank you.',updated),('agent','Case closed after tenant confirmation.',updated)]
            for role,text,date in messages:
                engine.db.execute('INSERT INTO messages(ticket_id,role,text,created_at) VALUES (?,?,?,?)',(tid,role,text,date))
            actions=[('assessment','recorded',f'Fictional assessment: {issue}; {urgency} priority.',0,None),
                     ('telegram','simulated',f'{tid}: Manager notification for unit {unit}. {summary}',1,None)]
            if i in [1,2,6]:
                actions.append(('email','failed','Fictional urgent manager email.',1,'Simulated provider failure. No real email was sent.'))
            if i==12:
                actions.append(('telegram','uncertain','Fictional tenant acknowledgement.',1,'Simulated delivery timeout. No external delivery occurred.'))
            if i==8:
                actions.append(('email','disabled','Email channel is disabled in this example.',0,'Email not configured; Telegram is the primary channel.'))
            for j,(kind,outcome,text,attempts,error) in enumerate(actions):
                payload={'text':text,'chat_id':config.manager,'subject':f'{tid}: Maintenance update','buttons':kind=='telegram'}
                engine.db.execute('INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?)',
                    (f'fixture-{i}-{j}',tid,kind,json.dumps(payload),outcome,attempts,error,updated,updated))
            added+=1
        # Add attachments to existing fictional reports without replacing user edits.
        for number, filename in [(1,'ceiling-leak'),(2,'damaged-socket'),(4,'dripping-ac')]:
            tid=f'DEMO-{number:04d}'
            engine.db.execute("""UPDATE messages SET photo=? WHERE id=(
                SELECT MIN(m.id) FROM messages m JOIN tickets t ON t.id=m.ticket_id
                WHERE m.ticket_id=? AND m.role='tenant' AND t.chat_id=?)
                AND (photo IS NULL OR photo='')""",
                ('/demo-photos/'+filename+'.jpg',tid,f'fixture-tenant-{number}'))
        # Dedicated slots keep fixture appointments separate from the existing rehearsal case.
        base=stamp.astimezone(timezone(timedelta(hours=8))).replace(hour=10,minute=0,second=0,microsecond=0)+timedelta(days=1)
        for n,(case,state) in enumerate([(3,'awaiting_approval'),(4,'booked'),(10,'offering'),(14,'awaiting_approval'),(16,'booked')]):
            tid=f'DEMO-{case:04d}'
            if engine.schedule(tid):
                continue
            offered=[]
            for option in range(2):
                sid=f'FIX{case}-{option}'
                start=base+timedelta(days=n%3,hours=option*4+(n//3)*2)
                engine.db.execute('INSERT OR IGNORE INTO inspection_slots VALUES (?,?,?,?,?,?)',
                    (sid,'Demo AC technician '+str(n+1),start.isoformat(),(start+timedelta(hours=1)).isoformat(),'hvac',tid if state=='booked' and option==0 else None))
                offered.append(sid)
            engine.db.execute('INSERT INTO scheduling VALUES (?,?,?,?,?,?)',
                (tid,state,json.dumps(offered),'[]',offered[0] if state!='offering' else None,1))
    print(f'Added {added} fictional cases to demo.sqlite3; existing records preserved.')
    print('No live database changes or external sends.')
    engine.db.close()


if __name__=='__main__':
    seed()
