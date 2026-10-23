/* Account-owned ranking intent. No discovery, providers, solver or background jobs. */
(() => {
  'use strict';
  const root = document.getElementById('my-dtos');
  if (!root) return;
  const el = id => document.getElementById(id), PAGE_SIZE = 25;
  let state = null, page = 0, busy = false, requestSequence = 0, controller = null, drag = null;
  const status = message => { el('personal-status').textContent = message; };
  function error(message) { el('personal-error').hidden = !message; el('personal-error').textContent = message || ''; }
  const value = number => typeof number === 'number' && Number.isFinite(number)
    ? number.toLocaleString(undefined, {maximumFractionDigits: 2}) : 'Unavailable';
  function node(tag, text, className) { const result = document.createElement(tag); if (text != null) result.textContent = text; if (className) result.className = className; return result; }
  const rowId = row => row.asset_id;
  const prefs = row => row.preferences || state?.preferences?.[rowId(row)] || {};
  function filtered() {
    const search = el('personal-search').value.trim().toLocaleLowerCase(), position = el('personal-position').value;
    const ordered = state?.mode === 'custom' ? (state?.rows || []) : [...(state?.rows || [])].sort((a, b) => (a.market_rank ?? Infinity) - (b.market_rank ?? Infinity));
    return ordered.map((row, index) => ({row, index})).filter(({row}) =>
      (!position || String(row.position || (row.asset_type === 'pick' ? 'PICK' : '')).toUpperCase() === position)
      && (!search || [row.label, row.asset_id, row.original_franchise_name, row.year, row.season].filter(Boolean).join(' ').toLocaleLowerCase().includes(search)));
  }
  function button(text, accessible, operation, focusKey) {
    const control = node('button', text, 'btn'); control.type = 'button'; control.setAttribute('aria-label', accessible);
    if (focusKey) control.dataset.focusKey = focusKey;
    control.disabled = busy || !state?.initialized || state.mode !== 'custom'; control.addEventListener('click', operation); return control;
  }
  function render(focusKey, scrollTop) {
    if (!state) return;
    const initialized = Boolean(state.initialized), custom = state.mode === 'custom';
    el('personal-neutral').setAttribute('aria-pressed', String(!custom));
    el('personal-custom').setAttribute('aria-pressed', String(custom));
    el('personal-neutral').disabled = busy; el('personal-custom').disabled = busy;
    el('personal-initialize').hidden = initialized;
    el('personal-initialize').disabled = busy || !state.rows?.length;
    el('personal-restart').hidden = !initialized;
    el('personal-restart').disabled = busy || !initialized || !state.rows?.length;
    el('personal-reload').disabled = busy;
    const scope = state.account_scope || state.context || {};
    el('personal-scope').textContent = `League ${scope.league_id || 'unavailable'} · Franchise ${scope.roster_id || 'unavailable'} · ${state.rows?.length || 0} eligible ranked assets · Revision ${state.revision || 0}`;
    el('personal-mode-description').textContent = custom
      ? 'Your personal values guide Custom decisions. Neutral Market fairness stays visible.'
      : 'Neutral Market values are active. Your custom order and preferences are preserved.';
    const method = state.method_explanation || (typeof state.method === 'object' ? state.method?.description : null);
    if (method) el('personal-method').textContent = method;
    const rows = filtered(); const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE)); page = Math.min(page, pages - 1);
    const list = el('personal-list'); list.replaceChildren();
    for (const {row, index} of rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)) {
      const id = rowId(row), label = row.label || id, rank = index + 1, editable = initialized && custom && row.custom_ranked !== false;
      const item = node('li', null, 'personal-row'); item.dataset.assetId = id; item.dataset.overallRank = String(rank); item.value = rank;
      const header = node('div', null, 'personal-row-heading');
      const handle = button('↕', `Drag ${label} to another overall position`, () => {}, `${id}:drag`);
      handle.disabled ||= !editable; handle.classList.add('personal-drag'); handle.draggable = !handle.disabled; handle.dataset.dragHandle = id; header.append(handle);
      const identity = node('div', null, 'personal-identity'); identity.append(node('strong', `${rank}. ${label}`), node('span', `${row.position || 'PICK'} · ${row.owned ? 'Your asset' : 'Not on your franchise'}`, 'muted')); header.append(identity); item.append(header);
      const values = node('p', null, 'personal-values'); values.append(node('span', `Market ${value(row.market_value)}`), node('span', `Personal ${value(row.personal_value)}`)); item.append(values);
      if (row.market_rank != null) item.append(node('p', `Current Market overall #${row.market_rank}${row.personal_rank != null ? ` · Your overall #${row.personal_rank}` : ''}`, 'muted'));
      if (initialized && row.custom_ranked === false) item.append(node('p', 'New eligible asset: not in your saved Custom baseline. Restart Rankings to include it in personal calculations.', 'personal-qualification'));
      if (row.limitation || row.unavailable_reason) item.append(node('p', row.limitation || row.unavailable_reason, 'personal-qualification'));
      const controls = node('div', null, 'personal-reorder');
      const move = (destination, key = `${id}:position`) => command('reorder', {asset_id: id, to_position: destination}, key);
      const up = button('Move Up', `Move ${label} up one overall position`, () => move(rank - 1, `${id}:up`), `${id}:up`); up.disabled ||= !editable || rank <= 1;
      const down = button('Move Down', `Move ${label} down one overall position`, () => move(rank + 1, `${id}:down`), `${id}:down`); down.disabled ||= !editable || rank >= state.rows.length;
      controls.append(up, down);
      const moveLabel = node('label', 'Overall position'); moveLabel.className = 'personal-move-label';
      const input = document.createElement('input'); input.type = 'number'; input.min = '1'; input.max = String(state.rows.length); input.value = String(rank); input.inputMode = 'numeric'; input.dataset.focusKey = `${id}:position`; input.setAttribute('aria-label', `Overall position for ${label}`); input.disabled = busy || !editable; moveLabel.append(input); controls.append(moveLabel);
      const moveButton = button('Move', `Move ${label} to entered overall position`, () => { const destination = Number(input.value); if (!Number.isInteger(destination) || destination < 1 || destination > state.rows.length) { error('Enter an available overall ranking position.'); input.focus(); return; } move(destination); }, `${id}:move`); moveButton.disabled ||= !editable; controls.append(moveButton); item.append(controls);
      const flags = node('div', null, 'personal-flags');
      for (const [flag, caption] of [['target', 'Target acquisition'], ['avoid', 'Prefer to avoid acquiring'], ['protect', 'Protect outgoing']]) {
        const wrap = node('label', null, 'personal-flag'); const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = Boolean(prefs(row)[flag]); checkbox.dataset.focusKey = `${id}:${flag}`;
        checkbox.setAttribute('aria-label', `${caption}: ${label}`); checkbox.disabled = busy || !initialized || row.custom_ranked === false || (flag === 'protect' && !row.owned && !checkbox.checked);
        checkbox.addEventListener('change', () => command('preferences', {asset_id: id, preferences: {...prefs(row), [flag]: checkbox.checked}}, `${id}:${flag}`)); wrap.append(checkbox, document.createTextNode(caption)); flags.append(wrap);
      }
      const tierLabel = node('label', null, 'personal-flag'); const tier = document.createElement('input'); tier.type = 'checkbox'; tier.checked = Boolean(row.tier_start || state.tiers?.includes(id)); tier.dataset.focusKey = `${id}:tier`; tier.disabled = busy || !editable; tier.setAttribute('aria-label', `Start personal tier at ${label}`); tier.addEventListener('change', () => command('tiers', {asset_id: id, tier_start: tier.checked}, `${id}:tier`)); tierLabel.append(tier, document.createTextNode('Start personal tier')); flags.append(tierLabel); item.append(flags);
      if (prefs(row).protect && !row.owned) item.append(node('p', 'Saved protection is inactive because this exact asset is not currently owned by your franchise.', 'personal-qualification'));
      list.append(item);
    }
    if (!rows.length) list.append(node('li', state.rows?.length ? 'No assets match these filters. Clear the search or position filter.' : 'Prepared compatible Market rankings are unavailable. Neutral browsing remains available; reload after Market is ready.', 'personal-empty'));
    el('personal-results-count').textContent = `${rows.length} matching assets · ${state.rows?.length || 0} in the complete ranking universe`;
    el('personal-page').textContent = `Page ${page + 1} of ${pages}`;
    el('personal-previous').disabled = busy || page === 0; el('personal-next').disabled = busy || page + 1 >= pages;
    if (scrollTop != null) window.scrollTo({top: scrollTop});
    if (focusKey) { const control = root.querySelector(`[data-focus-key="${CSS.escape(focusKey)}"]`); control?.focus({preventScroll: true}); if (control) { const bounds = control.getBoundingClientRect(); if (bounds.top < 0 || bounds.bottom > innerHeight - 80) control.scrollIntoView({block: 'nearest'}); } }
  }
  async function read() {
    if (busy) return;
    const sequence = ++requestSequence; controller?.abort(); controller = new AbortController(); status('Loading rankings…'); error('');
    try {
      const response = await fetch('/api/my-dtos', {credentials: 'same-origin', cache: 'no-store', signal: controller.signal}); const result = await response.json();
      if (sequence !== requestSequence) return;
      if (!response.ok) throw new Error(result.message || result.detail || 'My DTOS is unavailable. Sign in or reload and try again.');
      state = result; render(); status(result.limitations?.length ? result.limitations.join(' ') : 'Rankings loaded.');
    } catch (exc) { if (exc.name !== 'AbortError') { error(String(exc.message)); status('Rankings were not changed.'); } }
  }
  async function command(name, values = {}, focusKey) {
    if (busy || !state) return;
    const prior = state, scrollTop = window.scrollY, sequence = ++requestSequence; busy = true; error(''); render(focusKey, scrollTop); status('Saving your preference…');
    try {
      const response = await fetch('/api/my-dtos', {method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': prior.csrf_token}, body: JSON.stringify({command: name, expected_revision: prior.revision || 0, market_generation: prior.generation, context: prior.context, ...values})});
      const result = await response.json(); if (sequence !== requestSequence) return;
      if (!response.ok) throw new Error(result.message || result.detail || 'This change could not be saved. Reload before trying again.');
      if (prior.account_scope && result.account_scope && (prior.account_scope.league_id !== result.account_scope.league_id || prior.account_scope.roster_id !== result.account_scope.roster_id)) throw new Error('Your account or league changed. Reload before continuing.');
      state = result;
      if (focusKey) { const id = focusKey.slice(0, focusKey.lastIndexOf(':')); const index = filtered().findIndex(item => rowId(item.row) === id); if (index >= 0) page = Math.floor(index / PAGE_SIZE); }
      status(`Saved. Revision ${result.revision}.`);
    } catch (exc) { state = prior; error(String(exc.message)); status('The requested change was not applied to this view. Reload to review saved state.'); }
    finally { busy = false; render(focusKey, scrollTop); }
  }
  function startRestart() {
    el('personal-reset-flags').checked = false;
    const dialog = el('personal-restart-dialog'); if (typeof dialog.showModal === 'function') dialog.showModal(); else { dialog.setAttribute('open', ''); el('personal-restart-cancel').focus(); }
  }
  el('personal-neutral').onclick = () => { if (!state?.initialized) { status('Neutral DTOS is active. No saved rankings were created.'); return; } command('mode', {mode: 'neutral'}, ''); };
  el('personal-custom').onclick = () => state?.initialized ? command('mode', {mode: 'custom'}, '') : command('initialize', {}, '');
  el('personal-initialize').onclick = () => command('initialize');
  el('personal-reload').onclick = read;
  el('personal-restart').onclick = startRestart;
  el('personal-restart-cancel').onclick = () => { el('personal-restart-dialog').close(); el('personal-restart').focus(); };
  el('personal-restart-confirm').onclick = () => { const reset = el('personal-reset-flags').checked; el('personal-restart-dialog').close(); command('restart', {confirmation: 'RESTART RANKINGS', reset_preferences: reset}); };
  for (const id of ['personal-search', 'personal-position']) el(id).addEventListener(id === 'personal-search' ? 'input' : 'change', () => { page = 0; render(); });
  el('personal-previous').onclick = () => { page--; render(); el('personal-list').scrollIntoView({block: 'start'}); };
  el('personal-next').onclick = () => { page++; render(); el('personal-list').scrollIntoView({block: 'start'}); };
  root.addEventListener('dragstart', event => { const handle = event.target.closest('[data-drag-handle]'); if (!handle || busy || !state?.initialized || state.mode !== 'custom') { event.preventDefault(); return; } drag = {id: handle.dataset.dragHandle}; event.dataTransfer.setData('text/plain', drag.id); event.dataTransfer.effectAllowed = 'move'; });
  root.addEventListener('dragover', event => { const target = event.target.closest('[data-overall-rank]'); if (!drag || !target) return; event.preventDefault(); root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); target.classList.add('personal-drop-target'); });
  root.addEventListener('drop', event => { const target = event.target.closest('[data-overall-rank]'); if (!drag || !target) return; event.preventDefault(); const id = drag.id; drag = null; command('reorder', {asset_id: id, to_position: Number(target.dataset.overallRank)}, `${id}:drag`); });
  root.addEventListener('dragend', () => { drag = null; root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); });
  root.addEventListener('pointerdown', event => { if (event.pointerType === 'mouse') return; const handle = event.target.closest('[data-drag-handle]'); if (!handle || handle.disabled) return; event.preventDefault(); drag = {id: handle.dataset.dragHandle, pointer: event.pointerId, handle}; handle.setPointerCapture(event.pointerId); });
  root.addEventListener('pointermove', event => { if (!drag || drag.pointer !== event.pointerId) return; const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-overall-rank]'); root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); if (target) { target.classList.add('personal-drop-target'); drag.destination = Number(target.dataset.overallRank); } });
  root.addEventListener('pointerup', event => { if (!drag || drag.pointer !== event.pointerId) return; const {id, destination} = drag; drag = null; root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); if (destination) command('reorder', {asset_id: id, to_position: destination}, `${id}:drag`); });
  // Native HTML dragging cancels its initiating pointer. Only cancel the
  // separately captured touch gesture here; native dragend owns mouse cleanup.
  root.addEventListener('pointercancel', event => { if (!drag || drag.pointer !== event.pointerId) return; drag = null; root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); });
  addEventListener('pagehide', () => { requestSequence++; controller?.abort(); drag = null; });
  addEventListener('pageshow', event => { if (event.persisted) { busy = false; read(); } });
  read();
})();
