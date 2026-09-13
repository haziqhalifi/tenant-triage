/* Audio time is the clock, so pauses and seeking cannot drift from the scenes. */
if (new URLSearchParams(location.search).has('narration')) {
  const player = document.createElement('audio');
  player.src = '/narration.m4a';
  player.preload = 'auto';
  const dock = document.createElement('div');
  dock.className = 'narration-dock';
  const start = document.createElement('button');
  start.className = 'primary';
  start.textContent = 'Play narrated walkthrough';
  dock.append(start);
  document.body.append(player, dock);
  let original, scene = -1;
  const cues = [0, 6.86, 21.28, 30.94, 33.64, 37.42, 41.4, 44.5, 47.54, 57.28, 63.10, 67.5, 72.26, 78.2, 80.92, 92.76, 104.64, 114.96];
  const close = () => { if ($('#case-dialog').open) $('#case-dialog').close(); };
  const focus = element => element?.scrollIntoView({behavior: 'smooth', block: 'center'});
  const message = words => focus([...document.querySelectorAll('.conversation .message')].find(el => el.textContent.includes(words)));
  const heading = words => focus([...document.querySelectorAll('#case-content h3')].find(el => el.textContent.includes(words)));
  function showAt(time) {
    const next = cues.findLastIndex(cue => cue <= time);
    if (next === scene || !original) return;
    scene = next;
    // Reconstruct the illustrative view on every cue, including backward seeks.
    state = structuredClone(original);
    const ac = state.scheduling.find(item => item.ticket_id === 'DEMO-0003');
    if (ac) ac.state = time < 78.2 ? 'awaiting_approval' : 'booked';
    if (time < 78.2) state.messages = state.messages.filter(item =>
      item.ticket_id !== 'DEMO-0003' || !item.text.startsWith('Local inspection reservation confirmed:'));
    const leak = state.tickets.find(item => item.id === 'DEMO-0001');
    if (leak && time < 47.54) {
      leak.urgency = 'medium';
      leak.due_at = new Date(new Date(leak.created_at).getTime() + 48*3600000).toISOString();
    }
    close();
    if (next === 0 || next >= 14) {
      go('overview');
      if (next === 15) focus(document.querySelector('.approval-panel'));
      else window.scrollTo({top: 0, behavior: 'smooth'});
    } else {
      showCase(next >= 10 ? 'DEMO-0003' : 'DEMO-0001');
      requestAnimationFrame(() => {
        if (next === 1) heading('Report photo');
        if (next === 2) message('Is it dripping now');
        if (next === 3) message('Is anything electrical');
        if (next === 4 || next === 5) focus(document.querySelector('.case-heading'));
        if (next === 6) heading('Internal notes');
        if (next === 7) heading('Manager notification');
        if (next === 8) message('The leak is getting worse');
        if (next === 9) message('Any update?');
        if (next === 10) message('Which room is affected');
        if (next === 11) message('Available local inspection option');
        if (next === 12 || next === 13) heading('Inspection');
      });
    }
  }
  async function begin() {
    await refresh(true);
    if (state.mode !== 'demo' || !['DEMO-0001','DEMO-0003'].every(id => state.tickets.some(t => t.id === id))) {
      error('This walkthrough requires the existing sample cases.');
      return;
    }
    original = structuredClone(state);
    window.unitcueNarrationActive = true;
    document.body.classList.add('narration-playing');
    dock.hidden = true;
    scene = -1;
    player.currentTime = 0;
    showAt(0);
    try { await player.play(); } catch {
      stop();
      error('Could not play the narration. Check the audio file and try again.');
    }
  }
  function stop() {
    player.pause();
    close();
    window.unitcueNarrationActive = false;
    document.body.classList.remove('narration-playing');
    dock.hidden = false;
    if (original) state = structuredClone(original);
    go('overview');
    window.scrollTo({top: 0, behavior: 'smooth'});
  }
  start.addEventListener('click', begin);
  player.addEventListener('timeupdate', () => showAt(player.currentTime));
  player.addEventListener('ended', stop);
  player.addEventListener('error', () => { if (window.unitcueNarrationActive) stop(); });
  document.addEventListener('keydown', event => {
    if (!window.unitcueNarrationActive) return;
    if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); stop(); }
    if (event.code === 'Space') {
      event.preventDefault(); event.stopImmediatePropagation();
      if (player.paused) player.play(); else player.pause();
    }
  }, true);
}
