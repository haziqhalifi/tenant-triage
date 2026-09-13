const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state, busy = false, lastMessages = '', lastTickets = '', lastActions = '', pendingMessage;
const clock = value => new Date(value).toLocaleTimeString('en-MY', {hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kuala_Lumpur'});
const label = value => String(value).replaceAll('_',' ');
function error(message) { $('#error').textContent = message; $('#error').hidden = !message; }
async function refresh() {
  const response = await fetch('/api/state');
  if (!response.ok) throw new Error('Cannot load the maintenance desk. Check that the local server is running.');
  state = await response.json();
  $('#mode').textContent = state.mode === 'demo' ? 'Demo workspace' : 'Live workspace';
  $('#notice').textContent = state.mode === 'demo' ? 'Rehearsal mode. Triage uses local rules; Telegram and email actions are simulated. No external messages are sent.' : 'Live mode. Use the registered Telegram chats to report, acknowledge, and close cases. This console is read-only.';
  $('#property').textContent = state.property;
  $('#tenant').textContent = state.tenant + ' · Tenant';
  $('#unit').textContent = 'Unit ' + state.unit;
  $('#provider').textContent = state.model;
  $('#count').textContent = state.tickets.filter(t => t.status !== 'closed').length + ' active';
  $('#demo-controls').hidden = state.mode !== 'demo';
  $('#fail-email').hidden = state.mode !== 'demo';
  $('#fail-email').textContent = state.email_failure_armed ? 'Next email will fail (demo)' : 'Simulate next email failure';
  const ms = JSON.stringify(state.messages);
  if (ms !== lastMessages) {
    $('#messages').innerHTML = state.messages.length ? state.messages.map(m => `<div class="bubble ${esc(m.role)}"><small>${esc(m.role === 'tenant' ? state.tenant : m.role === 'agent' ? 'TenantTriage' : 'Property manager')} · ${clock(m.created_at)}</small>${esc(m.text)}${m.photo ? '<br>📎 Photo attached to report' : ''}</div>`).join('') : '<div class="empty-chat"><strong>It starts with a message.</strong>Report a maintenance issue below. The agent will ask for missing details and keep the case moving.</div>';
    $('#messages').scrollTop = $('#messages').scrollHeight; lastMessages = ms;
  }
  const ts = JSON.stringify(state.tickets);
  if (ts !== lastTickets) {
    $('#tickets').innerHTML = state.tickets.length ? state.tickets.map(t => `<div class="ticket ${esc(t.urgency)}"><div class="ticket-top"><span class="ticket-id">${esc(t.id)}</span><span class="badge ${esc(t.urgency)}">${esc(t.urgency)} priority</span></div><h3>${esc(t.issue_type === 'hvac' ? 'Air conditioning' : t.issue_type.charAt(0).toUpperCase() + t.issue_type.slice(1))} / ${esc(t.unit)}</h3><span class="badge ${esc(t.status)}">${esc(label(t.status))}</span><p>${esc(t.summary)}</p>${t.question ? `<p class="question">Awaiting tenant: ${esc(t.question)}</p>` : ''}<div class="meta"><span>Response target<br><strong>${t.urgency === 'crisis' ? 'Immediate attention' : esc(new Date(t.due_at).toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})) + ' MYT'}</strong></span><span>Owner<br><strong>Property manager</strong></span></div>${state.mode === 'demo' && t.status !== 'closed' ? `<div class="ticket-buttons">${t.status !== 'acknowledged' ? `<button class="primary" data-ack="${esc(t.id)}">Acknowledge case</button>` : ''}<button class="secondary" data-close="${esc(t.id)}">Close case</button></div>` : ''}</div>`).join('') : '<div class="empty-case"><span class="icon" aria-hidden="true">▤</span><h3>No open cases</h3>A tenant report will appear here with its priority, response target, and next action.</div>';
    lastTickets = ts;
  }
  const acts = JSON.stringify(state.actions);
  if (acts !== lastActions) {
    const expanded = new Set([...document.querySelectorAll('details[open]')].map(d => d.id));
    $('#actions').innerHTML = state.actions.length ? state.actions.map(a => `<div class="action"><time>${clock(a.created_at)}</time><details id="action-${esc(a.id)}" ${expanded.has('action-'+a.id) ? 'open' : ''}><summary>${esc(a.kind === 'assessment' ? 'Triage assessment' : a.kind === 'email' ? 'Manager email' : a.payload.buttons ? 'Manager notification' : 'Tenant reply')} <span class="ticket-id">${esc(a.ticket_id || '')}</span></summary><pre>${esc(a.payload.text)}${a.error ? '\n\n' + esc(a.error) : ''}</pre></details><div class="action-status"><span class="badge ${esc(a.status)}">${esc(a.status)}</span>${state.mode === 'demo' && ['failed','uncertain'].includes(a.status) ? `<button class="retry" data-retry="${esc(a.id)}">Retry</button>` : ''}</div></div>`).join('') : '<p class="empty-chat">Actions will appear after the first report.</p>';
    lastActions = acts;
  }
}
async function post(path, data) {
  if (busy || !state) return;
  busy = true; error(''); $('#send').disabled = true; $('#send').textContent = 'Processing…';
  try {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf}, body:JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Request failed');
    await refresh(); return result;
  } catch(e) { error(e.message); }
  finally { busy = false; $('#send').disabled = false; $('#send').textContent = 'Send message'; }
}
$('#composer').addEventListener('submit', async e => {
  e.preventDefault(); const text = $('#message').value.trim(); if(!text || busy) return;
  if(!pendingMessage || pendingMessage.text !== text) pendingMessage = {text,id:crypto.randomUUID()};
  if(await post('/api/message',pendingMessage)) { $('#message').value = ''; pendingMessage = undefined; }
});
document.addEventListener('click', async e => {
  const b = e.target.closest('button'); if(!b) return;
  if(b.dataset.message) { $('#message').value = b.dataset.message; $('#message').focus(); }
  if(b.dataset.ack) await post('/api/ack',{ticket_id:b.dataset.ack});
  if(b.dataset.close) await post('/api/close',{ticket_id:b.dataset.close});
  if(b.dataset.retry) await post('/api/retry',{action_id:b.dataset.retry});
});
$('#fail-email').addEventListener('click', async () => { await post('/api/fail-email',{}); });
refresh().catch(e => error(e.message));
setInterval(() => { if(!busy) refresh().catch(e => error(e.message)); }, 3500);
