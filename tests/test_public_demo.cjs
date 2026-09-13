const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const seed=JSON.parse(fs.readFileSync('public-demo/demo-state.json','utf8'));
const memory=new Map();
const context={window:{fetch:async()=>new Response(JSON.stringify(seed))},Response,crypto:require('node:crypto').webcrypto,localStorage:{getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)}};
vm.createContext(context);vm.runInContext(fs.readFileSync('web-demo/demo-runtime.js','utf8'),context);
async function api(path,body){const r=await context.window.fetch('/api/'+path,{body:JSON.stringify(body||{})});const result=await r.json();assert.equal(r.status,200,JSON.stringify(result));return result}
(async()=>{
 let state=await api('state');assert.equal(state.tickets.length,16);assert.equal(state.mode,'demo');
 const result=await api('message',{text:'My AC is not cold',id:'report1'});const tid=result.ticket_id;
 await api('message',{text:'I am free in the afternoon',id:'afternoon'});
 state=await api('state');let s=state.scheduling.find(x=>x.ticket_id===tid);assert.equal(s.state,'offering');
 await api('schedule',{action:'other',ticket_id:tid,revision:s.revision});
 state=await api('state');s=state.scheduling.find(x=>x.ticket_id===tid);
 await api('schedule',{action:'pick',ticket_id:tid,revision:s.revision,slot:JSON.parse(s.offered)[0]});
 await api('schedule',{action:'approve',ticket_id:tid,revision:s.revision});
 state=await api('state');assert.equal(state.scheduling.find(x=>x.ticket_id===tid).state,'booked');
 await api('note',{ticket_id:tid,text:'Demo note'});await api('details',{ticket_id:tid,owner:'Demo manager',next_step:'Inspect'});
 const failed=state.actions.find(a=>a.status==='failed');await api('retry',{action_id:failed.id});
 await api('close',{ticket_id:tid});state=await api('state');assert.equal(state.tickets.find(t=>t.id===tid).status,'closed');assert.equal(state.slots.filter(s=>s.booked_by===tid).length,0);
 assert(memory.size);console.log('Public demo: fixtures, reporting, preferences, alternatives, approval, notes, retry, closure, and browser persistence passed.');
})().catch(e=>{console.error(e);process.exit(1)});
