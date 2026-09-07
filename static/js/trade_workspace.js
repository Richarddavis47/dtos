/* One temporary, account/session/league-bound proposal. No external execution. */
(() => {
  'use strict';
  document.querySelectorAll('[data-trade-proposal]').forEach(button => button.onclick = async () => {
    button.disabled = true;
    try {
      const proposal = JSON.parse(button.dataset.tradeProposal);
      const response = await fetch('/api/trades/workspace?front_office=' + proposal.active_roster_id, {credentials: 'same-origin'});
      if (!response.ok) throw new Error('Workspace unavailable');
      const w = await response.json();
      if (w.active_front_office !== proposal.active_roster_id) throw new Error('Franchise changed');
      for (const [owner, ids] of [[proposal.active_roster_id, proposal.assets_sent], [proposal.partner_roster_id, proposal.assets_received]]) {
        const assets = w.teams.find(t => t.roster_id === owner)?.assets || [];
        if (!Array.isArray(ids) || ids.some(id => !assets.some(a => a.asset_id === id))) throw new Error('Ownership changed');
      }
      sessionStorage.setItem('dtos-trade-workspace:' + w.workspace_context.binding, JSON.stringify({partner: proposal.partner_roster_id, selected: {sent: proposal.assets_sent, received: proposal.assets_received}, ownership: w.workspace_context.ownership_generation}));
      location.assign('/trades/create?front_office=' + proposal.active_roster_id);
    } catch (_) { button.textContent = 'Unable to open this proposal. Refresh the page and try again.'; button.disabled = false; }
  });
  const root = document.getElementById('trade-builder');
  if (!root) return;
  const el = id => document.getElementById(id), active = Number(root.dataset.frontOffice);
  const flow = root.dataset.tradeWorkflow.replace('-', '_');
  let workspace, revision = 0, side = 'sent', busy = false, entryBlocked = false;
  const selected = {sent: [], received: []}, filters = {sent: {q: '', pos: 'ALL'}, received: {q: '', pos: 'ALL'}};
  const team = id => workspace?.teams.find(t => t.roster_id === Number(id));
  const asset = id => workspace?.teams.flatMap(t => t.assets).find(a => a.asset_id === id);
  const label = a => a.raw_label || a.label;
  const partner = () => Number(el('trade-partner').value);
  const storageKey = () => 'dtos-trade-workspace:' + workspace.workspace_context.binding;
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
  function message(text, error = false) { const box = el('trade-result'); box.hidden = false; box.className = error ? 'tw-error' : ''; box.replaceChildren(node('p', text)); }
  function payload() { return {workflow: flow, active_roster_id: active, partner_roster_id: partner(), assets_sent: [...selected.sent], assets_received: [...selected.received], asset_id: flow === 'shop' ? selected.sent[0] : selected.received[0], workspace_context: workspace.workspace_context}; }
  function persist() { try { sessionStorage.setItem(storageKey(), JSON.stringify({partner: partner(), selected, ownership: workspace.workspace_context.ownership_generation})); } catch (_) { /* Storage-disabled browsing still works in this page. */ } }
  function changed() { const focusId = document.activeElement?.dataset.assetId; revision++; el('trade-result').hidden = true; persist(); paint(); if (focusId) root.querySelector('button[data-asset-id="' + CSS.escape(focusId) + '"]')?.focus(); }
  function toggle(which, id) { if (busy) return; if (selected[which].includes(id)) selected[which] = selected[which].filter(x => x !== id); else if (!selected.sent.includes(id) && !selected.received.includes(id)) selected[which].push(id); changed(); }
  function identity(a) {
    const box = node('span');
    if (a.kind === 'player' && a.headshot_url) { const image = node('img'); image.src = a.headshot_url; image.alt = ''; image.loading = 'lazy'; image.onerror = () => image.remove(); box.append(image); }
    box.append(node('b', label(a)), node('small', a.kind === 'pick' ? [a.season, 'Round ' + a.round, 'Original: ' + label(a)].join(' · ') : [a.position, a.nfl_team, a.positional_rank].filter(Boolean).join(' · ')));
    return box;
  }
  function assetRow(a, which, review = false) {
    const row = node('div', null, 'tw-asset'), button = node('button'); button.type = 'button'; button.append(identity(a));
    button.append(node('strong', a.trade_value == null ? 'Unavailable' : String(a.trade_value)));
    button.dataset.assetId = a.asset_id; button.setAttribute('aria-label', (selected[which].includes(a.asset_id) ? 'Remove ' : 'Add ') + label(a) + (which === 'sent' ? ' — you send' : ' — you receive'));
    button.setAttribute('aria-pressed', String(selected[which].includes(a.asset_id))); button.onclick = () => toggle(which, a.asset_id); row.append(button);
    if (a.kind === 'player') { const link = node('a', 'Dossier'); link.href = '/players/' + encodeURIComponent(a.asset_id.replace(/^player:/, '')); link.setAttribute('aria-label', 'Open ' + label(a) + ' player dossier'); row.append(link); }
    if (review) row.classList.add('tw-selected');
    return row;
  }
  function board(which) {
    const container = el('trade-' + which + '-board'), owner = team(which === 'sent' ? active : partner()), f = filters[which];
    container.replaceChildren(); container.setAttribute('aria-hidden', String(matchMedia('(max-width:760px)').matches && side !== which));
    container.append(node('h3', owner?.team_name || 'Choose a counterparty'));
    if (!owner) return;
    const teamLink = node('a', 'Open Team HQ'); teamLink.href = '/teams/' + owner.roster_id; container.append(teamLink);
    const search = node('input'); search.type = 'search'; search.value = f.q; search.placeholder = 'Search players or picks'; search.setAttribute('aria-label', which === 'sent' ? 'Search my assets' : 'Search their assets');
    const results = node('div'), chips = node('div', null, 'tw-filters');
    const positions = ['ALL', 'QB', 'RB', 'WR', 'TE', 'PICKS'].filter(p => p === 'ALL' || owner.assets.some(a => (a.kind === 'pick' ? 'PICKS' : a.position) === p));
    function renderRows() { results.replaceChildren(); const rows = owner.assets.filter(a => (f.pos === 'ALL' || (a.kind === 'pick' ? 'PICKS' : a.position) === f.pos) && label(a).toLowerCase().includes(f.q.trim().toLowerCase())); for (const a of rows) results.append(assetRow(a, which)); if (!rows.length) results.append(node('p', owner.assets.length ? 'No matching assets. Clear search or choose All.' : 'No currently owned assets available.')); }
    search.oninput = () => { f.q = search.value; renderRows(); };
    for (const pos of positions) { const b = node('button', pos); b.type = 'button'; b.dataset.position = pos; b.setAttribute('aria-pressed', String(f.pos === pos)); b.onclick = () => { f.pos = pos; board(which); container.querySelector('[data-position="' + pos + '"]').focus(); }; chips.append(b); }
    container.append(search, chips, results); renderRows();
  }
  function paint() {
    board('sent'); board('received');
    const targetBox = el('trade-target'), targetId = flow === 'trade_for' ? selected.received[0] : flow === 'shop' ? selected.sent[0] : null, target = asset(targetId);
    targetBox.replaceChildren(); targetBox.hidden = !target || entryBlocked;
    if (target && !entryBlocked) {
      targetBox.append(node('h3', flow === 'shop' ? 'Asset you are shopping' : 'Player or pick you want'), identity(target));
      const owner = workspace.teams.find(t => t.assets.some(a => a.asset_id === targetId));
      const ownerLink = node('a', 'Current owner: ' + owner.team_name); ownerLink.href = '/teams/' + owner.roster_id; targetBox.append(ownerLink);
      if (target.kind === 'player') { const dossier = node('a', 'Open player dossier'); dossier.href = '/players/' + encodeURIComponent(target.asset_id.replace(/^player:/, '')); targetBox.append(dossier); }
    }
    for (const which of ['sent', 'received']) { const box = el('trade-' + which + '-chips'); box.replaceChildren(); for (const id of selected[which]) { const a = asset(id); if (a) box.append(assetRow(a, which, true)); else box.append(node('p', 'An asset is no longer available. Refresh this workspace.')); } }
    const count = selected.sent.length + selected.received.length;
    el('trade-tray').hidden = !count; el('trade-tray-text').textContent = `Trade proposal · ${count} assets · Send ${selected.sent.length} / Receive ${selected.received.length}`;
    const totals = which => { const rows = selected[which].map(asset); return rows.length && rows.every(a => a && a.trade_value != null) ? rows.reduce((sum, a) => sum + a.trade_value, 0) : null; };
    const sent = totals('sent'), received = totals('received'), balance = el('trade-balance'); balance.replaceChildren(node('h3', 'Market Balance'), node('p', `You send: ${sent ?? 'Unavailable'} · You receive: ${received ?? 'Unavailable'}`), node('small', 'Neutral market relationship only — not the Trade Intelligence recommendation.'));
    el('trade-context').textContent = `${team(active)?.team_name || 'Your franchise'} → ${team(partner())?.team_name || 'Choose partner'} · Active league ${workspace.manager_context.league_id}`;
    el('trade-run').disabled = busy || !selected.sent.length || !selected.received.length;
  }
  function review() { el('trade-review').hidden = false; el('trade-board').hidden = true; el('trade-review').focus(); }
  function edit() { el('trade-board').hidden = false; el('trade-review').hidden = true; el('trade-assist').hidden = true; el('trade-partner').focus(); }
  async function post(path, extra = {}) {
    const response = await fetch('/api/trades/' + path, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': workspace.csrf_token}, body: JSON.stringify({...payload(), ...extra})});
    let body; try { body = await response.json(); } catch (_) { throw new Error("DTOS couldn't complete this evaluation. Your proposal is still intact."); }
    if (!response.ok) {
      const d = body.detail; const code = typeof d === 'string' ? d : d?.code || body.status;
      if (code === 'csrf_rejected' || code === 'authentication_required') throw new Error('Your secure session needs refreshing. Your proposal is still intact. Reload and sign in if needed.');
      if (code === 'workspace_context_changed' || code === 'unauthorized_league' || code === 'unauthorized_franchise') throw new Error('This workspace belongs to a different account, league or franchise. Reload before evaluating.');
      throw new Error(d?.message || (typeof d === 'string' ? d : "DTOS couldn't complete this evaluation. Your proposal is still intact."));
    }
    return body;
  }
  function showEvaluation(e) {
    const out = el('trade-result'); out.hidden = false; out.className = ''; out.replaceChildren(node('h3', e.recommendation), node('p', e.dominant_reason));
    for (const [title, value] of [['Why you may do it', e.why_you_would_do_it], ['Why they may do it', e.why_they_would_do_it]]) if (value) out.append(node('h4', title), node('p', value));
    for (const [key, dim] of Object.entries(e.dimensions || {})) if (dim && dim.assessment) {
      const detail = node('details'); detail.append(node('summary', (dim.label || key.replaceAll('_', ' ')) + ': ' + dim.assessment));
      if (dim.explanation) detail.append(node('p', dim.explanation));
      for (const reason of dim.reasons || []) detail.append(node('p', reason));
      out.append(detail);
    }
    for (const [which, title] of [['active', 'Your team'], ['partner', 'Their team']]) {
      const impact = e.lineup_impact?.[which], quality = e.dimensions?.package_quality?.[which];
      if (quality) out.append(node('p', title + ' package: ' + quality.assessment), node('small', quality.explanation));
      if (impact) out.append(node('p', title + ' projected lineup change: ' + (impact.delta == null ? 'Unavailable' : String(impact.delta))), node('small', impact.delta == null ? impact.post?.reason || impact.pre?.reason || 'Canonical projection evidence is incomplete.' : 'Optimal legal lineup, before versus after.'));
    }
    if (e.why_now) out.append(node('h4', 'Why now'), node('p', e.why_now));
  }
  function openOffer(row) { el('trade-partner').value = String(row.proposal.partner_roster_id); selected.sent = [...row.proposal.assets_sent]; selected.received = [...row.proposal.assets_received]; changed(); review(); showEvaluation(row.evaluation); }
  function offers(body) {
    if (!body.results?.length) return message(body.quiet_state || 'No credible adjustment found. Your proposal is unchanged.');
    const out = el('trade-result'); out.hidden = false; out.replaceChildren();
    for (const row of body.results) { const b = node('button', 'Open editable offer: ' + (row.proposal_presentation?.send || []).map(a => a.label).join(' + ') + ' → ' + (row.proposal_presentation?.receive || []).map(a => a.label).join(' + ')); b.type = 'button'; b.onclick = () => openOffer(row); out.append(b); }
  }
  async function run(path, extra = {}) {
    if (busy || !workspace) return;
    if (path === 'generate' && entryBlocked) return;
    if (path === 'generate' && ((flow === 'shop' && selected.sent.length !== 1) || (flow === 'trade_for' && selected.received.length !== 1))) return message('Choose one target asset for this search. Multi-asset proposals can still be evaluated directly.', true);
    if (path === 'assist') {
      const text = (extra.instruction || '').trim().toLowerCase();
      extra.repair_mode = text === 'alternative target' ? 'ALTERNATIVE_TARGET' : text === 'alternative construction' ? 'ALTERNATIVE_CONSTRUCTION' : 'MAKE_THIS_TRADE_WORK';
    }
    busy = true; const started = revision; paint(); message('Working on your proposal…');
    try {
      const body = await post(path, extra);
      if (started !== revision) return;
      if (path === 'assist' && (body.requested_mode !== extra.repair_mode || body.returned_modes?.some(mode => mode !== extra.repair_mode) || (body.results?.length && extra.repair_mode !== 'ALTERNATIVE_TARGET' && (body.target_preserved !== true || body.results.some(row => row.proposal.assets_received.length !== selected.received.length || row.proposal.assets_received.some(id => !selected.received.includes(id))))))) throw new Error('DTOS rejected a mismatched repair mode. Your proposal is unchanged.');
      if (path === 'evaluate') { review(); showEvaluation(body.evaluation); } else offers(body);
    } catch (error) { message(error.message, true); } finally { busy = false; paint(); }
  }
  el('trade-view').onclick = review; el('trade-tray-view').onclick = review; el('trade-edit').onclick = edit;
  el('trade-run').onclick = () => run('evaluate'); el('trade-find').onclick = () => run('generate');
  el('trade-adjust').onclick = () => { el('trade-assist').hidden = false; el('trade-instruction').focus(); };
  el('trade-apply-adjust').onclick = () => run('assist', {instruction: el('trade-instruction').value || 'make this trade work'});
  root.querySelectorAll('[data-adjust]').forEach(b => b.onclick = () => { el('trade-instruction').value = b.dataset.adjust; });
  root.querySelectorAll('[data-side]').forEach(b => b.onclick = () => { side = b.dataset.side; root.querySelectorAll('[data-side]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); paint(); });
  el('trade-partner').onchange = () => { selected.received = []; changed(); };
  matchMedia('(max-width:760px)').addEventListener('change', () => { if (workspace) paint(); });
  fetch('/api/trades/workspace?front_office=' + active, {credentials: 'same-origin'}).then(async response => { if (!response.ok) throw new Error('Unable to load this authorized workspace.'); return response.json(); }).then(data => {
    workspace = data;
    try { for (const key of Object.keys(sessionStorage)) if (key.startsWith('dtos-trade-workspace:') && key !== storageKey()) sessionStorage.removeItem(key); } catch (_) { /* Storage is optional. */ }
    for (const t of data.teams) if (t.roster_id !== active) { const option = node('option', t.team_name); option.value = t.roster_id; el('trade-partner').append(option); }
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey()) || 'null');
      if (saved && team(saved.partner) && Array.isArray(saved.selected?.sent) && Array.isArray(saved.selected?.received)) {
        el('trade-partner').value = saved.partner; selected.sent = saved.selected.sent; selected.received = saved.selected.received;
        if (saved.ownership !== data.workspace_context.ownership_generation) message('Ownership has changed. Your proposal is retained for review; evaluation will identify any assets that moved.', true);
      }
    } catch (_) { /* No persisted draft is required. */ }
    const preload = root.dataset.preloadAsset;
    if (preload) { const owner = data.teams.find(t => t.assets.some(a => a.asset_id === preload)); if (!owner || (flow === 'shop' && owner.roster_id !== active) || (flow === 'trade_for' && owner.roster_id === active)) { entryBlocked = true; el('trade-find').disabled = true; message('This asset is not currently owned by the required franchise. Review current ownership or choose another Trade Center entry.', true); } else { if (flow === 'shop') selected.sent = [preload]; else { el('trade-partner').value = owner.roster_id; selected.received = [preload]; } } }
    el('trade-find').hidden = flow === 'create'; paint();
  }).catch(error => message(error.message, true));
})();
