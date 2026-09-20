/* One temporary, account/session/league-bound proposal. No external execution. */
(() => {
  'use strict';
  // Presentation only: retain canonical precision and unavailable evidence.
  function displayPoints(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return 'Unavailable';
    const displayed = value.toFixed(2);
    return displayed === '-0.00' ? '0.00' : displayed;
  }
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
  let shopTarget = flow === 'shop' ? root.dataset.preloadAsset || null : null;
  const excludedFamilies = new Set(); let displayedFamilies = [];
  const selected = {sent: [], received: []}, filters = {sent: {q: '', pos: 'ALL'}, received: {q: '', pos: 'ALL'}};
  const team = id => workspace?.teams.find(t => t.roster_id === Number(id));
  const asset = id => workspace?.teams.flatMap(t => t.assets).find(a => a.asset_id === id);
  const label = a => a.raw_label || a.label;
  const partner = () => Number(el('trade-partner').value);
  const storageKey = () => 'dtos-trade-workspace:' + workspace.workspace_context.binding;
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
  function message(text, error = false) { const box = el('trade-result'); box.hidden = false; box.className = error ? 'tw-error' : ''; box.replaceChildren(node('p', text)); }
  function payload() { return {workflow: flow, active_roster_id: active, partner_roster_id: partner(), assets_sent: [...selected.sent], assets_received: [...selected.received], asset_id: flow === 'shop' ? shopTarget || selected.sent[0] : selected.received[0], workspace_context: workspace.workspace_context}; }
  function persist() { try { sessionStorage.setItem(storageKey(), JSON.stringify({partner: partner(), selected, ownership: workspace.workspace_context.ownership_generation})); } catch (_) { /* Storage-disabled browsing still works in this page. */ } }
  function changed() { const focusId = document.activeElement?.dataset.assetId; revision++; el('trade-result').hidden = true; persist(); paint(); if (focusId) root.querySelector('button[data-asset-id="' + CSS.escape(focusId) + '"]')?.focus(); }
  function toggle(which, id) { if (busy) return; if (flow === 'shop' && which === 'sent' && id === shopTarget && selected.sent.includes(id)) return message('The shopped asset stays fixed. Choose Build My Own to leave this search.', true); if (selected[which].includes(id)) selected[which] = selected[which].filter(x => x !== id); else if (!selected.sent.includes(id) && !selected.received.includes(id)) selected[which].push(id); changed(); }
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
  function showEvaluation(e, opportunity = null) {
    const out = el('trade-result'); out.hidden = false; out.className = ''; out.replaceChildren(node('h3', e.recommendation || 'Assessment unavailable'), node('p', e.dominant_reason));
    if (e.legality?.execution_status) out.append(node('p', e.legality.execution_status));
    if (e.recommendation_trace) {
      const trace = node('details'); trace.append(node('summary', 'Recommendation evidence'));
      for (const reason of e.recommendation_trace.rule_reasons || []) trace.append(node('p', reason.replaceAll('_', ' ')));
      trace.append(node('small', e.recommendation_trace.scope)); out.append(trace);
    }
    for (const [title, value] of [['Why you may do it', e.why_you_would_do_it], ['Why they may do it', e.why_they_would_do_it]]) if (value) out.append(node('h4', title), node('p', value));
    for (const [key, dim] of Object.entries(e.dimensions || {})) if (dim && dim.assessment) {
      const detail = node('details'); detail.append(node('summary', (dim.label || key.replaceAll('_', ' ')) + ': ' + dim.assessment));
      if (dim.explanation) detail.append(node('p', dim.explanation));
      for (const reason of dim.reasons || []) detail.append(node('p', reason));
      if (key === 'confidence' && dim.dimensions) {
        const coverage = dim.dimensions;
        detail.append(node('p', `Market coverage: ${coverage.market.priced_assets}/${coverage.market.asset_count} assets (${coverage.market.availability}).`));
        detail.append(node('p', `FOIS context: ${coverage.fois.availability}. This is not an acceptance probability.`));
        for (const [side, horizons] of Object.entries(coverage.projection_and_lineup || {}))
          for (const [name, row] of Object.entries(horizons)) detail.append(node('p', `${side} · ${name.replaceAll('_', ' ')}: ${row.availability}`));
      }
      out.append(detail);
    }
    for (const [which, title] of [['active', 'Your team'], ['partner', 'Their team']]) {
      const impact = e.lineup_impact?.[which], quality = e.dimensions?.package_quality?.[which];
      if (quality) out.append(node('p', title + ' package: ' + quality.assessment), node('small', quality.explanation));
      if (impact) out.append(node('p', title + ' projected lineup change: ' + displayPoints(impact.delta)), node('small', impact.delta == null ? impact.post?.reason || impact.pre?.reason || 'Canonical projection evidence is incomplete.' : 'Optimal legal lineup, before versus after.'));
      const horizons = e.multi_horizon_impact?.sides?.[which]?.horizons || {};
      const strategy = e.dimensions?.strategic_fit?.[which];
      if (strategy) {
        const detail = node('details'); detail.append(node('summary', title + ' strategic evidence'));
        for (const reason of strategy.reason_codes || []) detail.append(node('p', reason.replaceAll('_', ' ')));
        if (strategy.roster_capacity) detail.append(node('p', `Additional configured roster spots to resolve: ${strategy.roster_capacity.additional_spots_to_resolve}. Cut cost is not assumed.`));
        if (strategy.unavailable_dimensions?.length) detail.append(node('small', 'Unavailable: ' + strategy.unavailable_dimensions.join(', ').replaceAll('_', ' ')));
        out.append(detail);
      }
      for (const [key, horizon] of Object.entries(horizons)) {
        const label = {current_week: 'Current week', next_n: 'Next-N', rest_of_regular_season: 'Rest of regular season', playoff_window: 'Playoff window'}[key] || key;
        out.append(node('p', `${title} · ${label}: ${displayPoints(horizon.delta)}`),
          node('small', `Supported weeks: before ${horizon.pre_supported_weeks.length}/${horizon.weeks_requested?.length || 0}; after ${horizon.post_supported_weeks.length}/${horizon.weeks_requested?.length || 0}. Optimal before versus optimal after.`));
        if (horizon.delta == null && horizon.supported_week_delta_subtotal != null)
          out.append(node('small', `Comparable-week change subtotal: ${displayPoints(horizon.supported_week_delta_subtotal)} across ${horizon.comparable_weeks.length} weeks. Not a complete horizon projection.`));
      }
    }
    if (opportunity) {
      out.append(node('h4', 'Why now · supported context'));
      for (const c of opportunity.why_now?.catalysts || []) out.append(node('p', `${c.side} · ${c.horizon.replaceAll('_', ' ')}: ${displayPoints(c.delta)}`), node('small', c.limitation));
      if (!opportunity.why_now?.catalysts?.length) out.append(node('p', 'No supported current catalyst is available.'));
      if (opportunity.stable_opportunity_reasons?.length) {
        out.append(node('h4', 'Supported trade fit — not urgency'));
        for (const c of opportunity.stable_opportunity_reasons) out.append(node('p', `${c.side} · ${c.horizon.replaceAll('_', ' ')}: ${displayPoints(c.delta)}`));
      }
    } else if (e.why_now) out.append(node('h4', 'Why now'), node('p', e.why_now));
    if (e.major_limitations?.length) out.append(node('h4', 'Evidence limitations'), node('p', e.major_limitations.join(', ').replaceAll('_', ' ')));
  }
  function openOffer(row) { el('trade-partner').value = String(row.proposal.partner_roster_id); selected.sent = [...row.proposal.assets_sent]; selected.received = [...row.proposal.assets_received]; changed(); review(); showEvaluation(row.evaluation, row.opportunity); }
  function offers(body) {
    if (flow === 'recommended' && body.workflow === 'recommended') {
      displayedFamilies = (body.results || []).map(row => row.family_id);
      const out = el('trade-result'); out.hidden = false; out.replaceChildren();
      if (!body.results?.length) out.append(node('p', body.quiet_state || 'No credible opportunity.'));
      for (const row of body.results || []) {
        out.append(node('h3', row.evaluation.recommendation), node('p', (row.opportunity?.reason_tags || []).join(' · ')));
        const b = node('button', 'Open editable offer: ' + (row.proposal_presentation?.send || []).map(a => a.label).join(' + ') + ' → ' + (row.proposal_presentation?.receive || []).map(a => a.label).join(' + ')); b.type = 'button'; b.onclick = () => openOffer(row); out.append(b);
      }
      for (const reason of body.discovery?.limitations || []) out.append(node('small', reason.replaceAll('_', ' ')));
      for (const [reason, count] of Object.entries(body.search_evidence?.rejection_reason_counts || {})) out.append(node('small', reason.replaceAll('_', ' ') + ': ' + count + ' evaluated candidates'));
      return;
    }
    if (flow === 'shop' && body.markets) {
      const out = el('trade-result'); out.hidden = false; out.replaceChildren();
      if (!body.markets.length) out.append(node('p', body.quiet_state || 'No credible market in this bounded search.'));
      for (const limitation of body.shop_preference?.limitations || []) out.append(node('p', limitation));
      for (const market of body.markets) {
        out.append(node('h3', team(market.counterparty_roster_id)?.team_name || 'Counterparty'),
          node('p', market.buyer_rationale?.explanation || 'Review the shared counterparty evidence.'));
        for (const row of market.returns) { const b = node('button', 'Open editable offer: ' + (row.proposal_presentation?.send || []).map(a => a.label).join(' + ') + ' → ' + (row.proposal_presentation?.receive || []).map(a => a.label).join(' + ')); b.type = 'button'; b.onclick = () => openOffer(row); out.append(b); }
      }
      if (!body.markets.length) for (const [reason, count] of Object.entries(body.search_evidence?.rejection_reason_counts || {})) out.append(node('small', reason.replaceAll('_', ' ') + ': ' + count + ' evaluated candidates'));
      return;
    }
    if (!body.results?.length) return message(body.quiet_state || 'No credible adjustment found. Your proposal is unchanged.');
    const out = el('trade-result'); out.hidden = false; out.replaceChildren();
    for (const row of body.results) { const b = node('button', 'Open editable offer: ' + (row.proposal_presentation?.send || []).map(a => a.label).join(' + ') + ' → ' + (row.proposal_presentation?.receive || []).map(a => a.label).join(' + ')); b.type = 'button'; b.onclick = () => openOffer(row); out.append(b); }
  }
  async function run(path, extra = {}) {
    if (busy || !workspace) return;
    if (path === 'generate' && entryBlocked) return;
    if (path === 'generate' && ((flow === 'shop' && !shopTarget && selected.sent.length !== 1) || (flow === 'trade_for' && selected.received.length !== 1))) return message('Choose one target asset for this search. Multi-asset proposals can still be evaluated directly.', true);
    if (path === 'generate' && flow === 'shop') {
      shopTarget = shopTarget || selected.sent[0];
      extra = {...extra, partner_roster_id: 0, asset_id: shopTarget,
        shop_preference: el('shop-preference').value,
        shop_position: el('shop-preference').value === 'position_need' ? el('shop-position').value : null,
        protected_assets: Array.from(el('shop-protected').selectedOptions, option => option.value)};
    }
    if (path === 'generate' && flow === 'recommended') extra = {...extra, partner_roster_id: 0, asset_id: null,
      recommendation_filter: el('recommendation-filter').value, excluded_recommendation_families: [...excludedFamilies]};
    if (path === 'assist') {
      extra.origin_workflow = flow;
      if (flow === 'shop') extra.origin_asset_id = shopTarget || selected.sent[0];
      const text = (extra.instruction || '').trim().toLowerCase();
      extra.repair_mode = text === 'alternative target' ? 'ALTERNATIVE_TARGET' : text === 'alternative construction' ? 'ALTERNATIVE_CONSTRUCTION' : 'MAKE_THIS_TRADE_WORK';
    }
    busy = true; const started = revision; paint(); message('Working on your proposal…');
    try {
      const body = await post(path, extra);
      if (started !== revision) return;
      if (path === 'assist') {
        const lostTarget = body.results?.some(row => selected.received.some(id => !row.proposal.assets_received.includes(id)));
        const invalidPreservation = body.results?.length && extra.repair_mode !== 'ALTERNATIVE_TARGET' && (body.target_preserved !== true || lostTarget);
        if (body.requested_mode !== extra.repair_mode || body.returned_modes?.some(mode => mode !== extra.repair_mode) || invalidPreservation) throw new Error('DTOS rejected a mismatched repair mode. Your proposal is unchanged.');
      }
      if (path === 'evaluate') { review(); showEvaluation(body.evaluation); } else offers(body);
    } catch (error) { message(error.message, true); } finally { busy = false; paint(); }
  }
  el('trade-view').onclick = review; el('trade-tray-view').onclick = review; el('trade-edit').onclick = edit;
  el('trade-run').onclick = () => run('evaluate'); el('trade-find').onclick = () => run('generate');
  el('trade-build-own').onclick = () => {
    if (busy || !workspace) return;
    try { sessionStorage.removeItem(storageKey()); } catch (_) { /* Storage is optional. */ }
    location.assign('/trades/create?front_office=' + active);
  };
  el('trade-adjust').onclick = () => { el('trade-assist').hidden = false; el('trade-instruction').focus(); };
  el('trade-apply-adjust').onclick = () => run('assist', {instruction: el('trade-instruction').value || 'make this trade work'});
  root.querySelectorAll('[data-adjust]').forEach(b => b.onclick = () => { el('trade-instruction').value = b.dataset.adjust; });
  root.querySelectorAll('[data-side]').forEach(b => b.onclick = () => { side = b.dataset.side; root.querySelectorAll('[data-side]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); paint(); });
  el('trade-partner').onchange = () => { selected.received = []; changed(); };
  matchMedia('(max-width:760px)').addEventListener('change', () => { if (workspace) paint(); });
  fetch('/api/trades/workspace?front_office=' + active, {credentials: 'same-origin'}).then(async response => { if (!response.ok) throw new Error('Unable to load this authorized workspace.'); return response.json(); }).then(data => {
    workspace = data;
    if (flow === 'recommended') {
      el('trade-find').textContent = 'Discover Recommended Trades';
      el('recommendation-refresh').onclick = () => {
        if (busy) return;
        for (const family of displayedFamilies) if (excludedFamilies.size < 64) excludedFamilies.add(family);
        run('generate');
      };
      el('recommendation-filter').onchange = () => { revision++; el('trade-result').hidden = true; };
    }
    if (flow === 'shop') {
      for (const a of team(active)?.assets || []) { const option = node('option', label(a)); option.value = a.asset_id; el('shop-protected').append(option); }
      el('shop-preference').onchange = () => { el('shop-position').disabled = el('shop-preference').value !== 'position_need'; revision++; el('trade-result').hidden = true; };
      for (const id of ['shop-position', 'shop-protected']) el(id).onchange = () => { revision++; el('trade-result').hidden = true; };
    }
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
