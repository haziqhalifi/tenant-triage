/* Static showcase adapter: all API operations are local simulations. */
(() => {
const originalFetch=window.fetch.bind(window), key='tenanttriage-public-v1';
let data;
const ready=originalFetch('/demo-state.json').then(r=>r.json()).then(seed=>{
 try{data=JSON.parse(localStorage.getItem(key))||seed}catch{data=seed}
 data.unlocked=true;data.mode='demo';data.csrf='public-demo';return data;
});
const now=()=>new Date().toISOString(), uuid=()=>crypto.randomUUID();
const ticket=id=>data.tickets.find(t=>t.id===id), schedule=id=>data.scheduling.find(s=>s.ticket_id===id);
const label=id=>{const s=data.slots.find(x=>x.id===id);return s?new Date(s.starts_at).toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur'})+' MYT / '+s.technician:'Unavailable slot'};
const addAction=(id,kind,text,status='simulated',extra={})=>{data.actions.unshift({id:uuid(),ticket_id:id,kind,payload:{text,...extra},status,attempts:status==='recorded'?0:1,error:status==='failed'?'Simulated provider failure. No message was sent.':null,created_at:now(),updated_at:now()})};
const message=(id,role,text)=>{data.messages.push({id:Date.now()+Math.random(),ticket_id:id,role,text,created_at:now()});if(role==='agent')addAction(id,'telegram',text)};
const offer=(id)=>{
 let s=schedule(id);if(!s){s={ticket_id:id,state:'offering',offered:'[]',rejected:'[]',selected:null,revision:0};data.scheduling.push(s)}
 const rejected=JSON.parse(s.rejected), available=data.slots.filter(x=>!x.booked_by&&!rejected.includes(x.id)&&new Date(x.starts_at)>new Date()).slice(0,2);
 s.revision++;s.selected=null;s.offered=JSON.stringify(available.map(x=>x.id));s.state=available.length?'offering':'needs_manager';
 message(id,'agent',available.length?'Choose an inspection slot in Appointments. Manager approval is required. These are fictional local reservations.\n'+available.map((x,i)=>`${i+1}. ${label(x.id)}`).join('\n'):'No further demo slots are available. Manager coordination is needed.');
};
function act(action,id,rev,slot){
 const s=schedule(id);if(!s||!ticket(id)||ticket(id).status==='closed')throw Error('Case unavailable for scheduling.');
 if(Number(rev)!==s.revision)throw Error('This offer has changed. Refresh and choose the latest slot.');
 if(['pick','other'].includes(action)){
  if(s.state!=='offering')throw Error('Offer is no longer open.');
  if(action==='other'){s.rejected=JSON.stringify([...JSON.parse(s.rejected),...JSON.parse(s.offered)]);offer(id)}
  else{if(!JSON.parse(s.offered).includes(slot))throw Error('Choose an offered slot.');s.selected=slot;s.state='awaiting_approval';message(id,'agent','Selected '+label(slot)+'. Awaiting manager approval; no booking yet.');addAction(id,'telegram','Tenant selected '+label(slot)+'. Manager approval required.','simulated',{buttons:true})}
 }else if(['approve','decline'].includes(action)){
  if(s.state==='booked'&&action==='approve')return;
  if(s.state!=='awaiting_approval')throw Error('No approval is pending.');
  const chosen=data.slots.find(x=>x.id===s.selected);
  if(action==='decline'||!chosen||chosen.booked_by||new Date(chosen.starts_at)<=new Date()){
   s.rejected=JSON.stringify([...JSON.parse(s.rejected),s.selected]);message(id,'agent','That slot was declined or is no longer available. Checking alternatives.');offer(id);
  }else{chosen.booked_by=id;s.state='booked';message(id,'agent','Demo reservation confirmed: '+label(chosen.id)+'. No real contractor or external calendar is involved.');addAction(id,'assessment','Manager approved simulated reservation.','recorded')}
 }else throw Error('Unknown scheduling action');
}
function report(body){
 if(typeof body.text!=='string'||!body.text.trim())throw Error('Enter a report.');
 data.demoUpdates??={};if(data.demoUpdates[body.id])return data.demoUpdates[body.id];
 const text=body.text.trim(),low=text.toLowerCase();let t=data.tickets.find(x=>x.chat_id==='public-rehearsal'&&x.status!=='closed');
 if(t){const s=schedule(t.id);if(s?.state==='offering'&&['1','2','another time','neither'].includes(low)){act(['1','2'].includes(low)?'pick':'other',t.id,s.revision,JSON.parse(s.offered)[Number(low)-1]);return {ticket_id:t.id}}}
 if(t&&schedule(t.id)?.state==='offering'&&/afternoon|morning/.test(low)){
  const s=schedule(t.id), rejected=JSON.parse(s.rejected), afternoon=low.includes('afternoon');
  const available=data.slots.filter(x=>!x.booked_by&&!rejected.includes(x.id)&&new Date(x.starts_at)>new Date()&&(afternoon?Number(x.starts_at.slice(11,13))>=12:Number(x.starts_at.slice(11,13))<12)).slice(0,2);
  s.offered=JSON.stringify(available.map(x=>x.id));s.revision++;s.state=available.length?'offering':'needs_manager';
  message(t.id,'agent',available.length?'Matching slots are available in Appointments. Select one to request manager approval.':'No matching demo slots. Manager coordination is needed.');return {ticket_id:t.id};
 }
 if(low==='/status'){if(t)message(t.id,'agent',`${t.id}: ${t.status}. Inspection: ${schedule(t.id)?.state||'not scheduled'}.`);return {ticket_id:t?.id}}
 if(!t){t={id:'TKT-'+uuid().slice(0,8).toUpperCase(),chat_id:'public-rehearsal',unit:'B-12-03',issue_type:'other',urgency:'low',summary:'',question:'',status:'open',needs_human:0,due_at:now(),created_at:now(),updated_at:now()};data.tickets.unshift(t)}
 message(t.id,'tenant',text);
 const previous=t.summary, combined=(previous+' '+text).toLowerCase();t.summary=(previous?previous+' / ':'')+text;t.updated_at=now();t.question='';
 if(/ac |aircon|not cold|air conditioning/.test(combined)){t.issue_type='hvac';t.urgency='medium'}
 else if(/leak|water|sink|tap/.test(combined)){t.issue_type='plumbing';t.urgency=/spreading|worse|flood/.test(combined)?'high':'medium';if(!previous)t.question='Is the water contained or continuing to spread?'}
 else if(/lease|deposit|evict/.test(combined)){t.issue_type='lease';t.needs_human=1}
 else{t.question='What is affected, and what is happening right now?';t.needs_human=previous?1:0}
 if(/spark|smoke|gas smell|on fire/.test(combined)){t.urgency='crisis';t.needs_human=1;t.question=''}
 t.status=t.needs_human?'escalated':t.question?'waiting_on_tenant':'open';
 t.due_at=new Date(Date.now()+({low:48,medium:48,high:2,crisis:0}[t.urgency])*3600000).toISOString();
 addAction(t.id,'assessment',`Local rule simulation: ${t.issue_type} / ${t.urgency}`,'recorded');
 addAction(t.id,'telegram',`${t.id}: ${t.summary}`,'simulated',{buttons:true});
 if(['high','crisis'].includes(t.urgency)||t.needs_human){addAction(t.id,'email','Simulated manager escalation.',data.email_failure_armed?'failed':'simulated');data.email_failure_armed=false}
 message(t.id,'agent',`${t.id}: ${t.urgency} priority. ${t.question||'Your report is ready for manager review.'} This is a local simulation.`);
 if(t.issue_type==='hvac'&&!t.needs_human&&!schedule(t.id))offer(t.id);
 const result={ticket_id:t.id};if(body.id)data.demoUpdates[body.id]=result;return result;
}
window.fetch=async(input,options={})=>{
 const path=typeof input==='string'?input:input.url;
 if(!path.startsWith('/api/'))return originalFetch(input,options);
 await ready;
 try{
  if(path==='/api/state')return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
  const b=JSON.parse(options.body||'{}');let result={ok:true};
  if(path==='/api/message')result=report(b);
  else if(path==='/api/ack'||path==='/api/close'){
   const t=ticket(b.ticket_id);if(!t)throw Error('Case not found');
   const target=path.endsWith('close')?'closed':'acknowledged';if(t.status!=='closed'&&t.status!==target){t.status=target;t.updated_at=now();if(target==='closed'){const s=schedule(t.id);if(s){s.state='closed';s.revision++}data.slots.forEach(x=>{if(x.booked_by===t.id)x.booked_by=null})}message(t.id,'agent',`Your manager has ${target} this demo case.`)}
  }else if(path==='/api/note'){if(!ticket(b.ticket_id)||!b.text?.trim())throw Error('Enter a note for an existing case.');data.notes.push({id:Date.now(),ticket_id:b.ticket_id,text:b.text,created_at:now()})}
  else if(path==='/api/details'){if(!ticket(b.ticket_id)||!b.owner?.trim())throw Error('Case and owner are required.');data.details=data.details.filter(x=>x.ticket_id!==b.ticket_id);data.details.push({ticket_id:b.ticket_id,owner:b.owner,next_step:b.next_step||''})}
  else if(path==='/api/retry'){const a=data.actions.find(x=>x.id===b.action_id);if(!a)throw Error('Action not found');a.status='simulated';a.error=null;a.attempts++;a.updated_at=now()}
  else if(path==='/api/fail-email')data.email_failure_armed=true;
  else if(path==='/api/schedule')act(b.action,b.ticket_id,b.revision,b.slot);
  else if(!['/api/login','/api/logout'].includes(path))throw Error('Unknown demo action.');
  try{localStorage.setItem(key,JSON.stringify(data))}catch{}
  return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}});
 }catch(e){return new Response(JSON.stringify({error:e.message}),{status:400,headers:{'Content-Type':'application/json'}})}
};
})();
