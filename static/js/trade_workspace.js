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
      const destination = button.dataset.tradeDestination === 'calculator' ? 'calculator' : 'create';
      const response = await fetch('/api/trades/workspace?front_office=' + proposal.active_roster_id + (destination === 'calculator' ? '&mode=calculator' : ''), {credentials: 'same-origin'});
      if (!response.ok) throw new Error('Workspace unavailable');
      const w = await response.json();
      if (w.active_front_office !== proposal.active_roster_id) throw new Error('Franchise changed');
      for (const [owner, ids] of [[proposal.active_roster_id, proposal.assets_sent], [proposal.partner_roster_id, proposal.assets_received]]) {
        const assets = w.teams.find(t => t.roster_id === owner)?.assets || [];
        if (!Array.isArray(ids) || ids.some(id => !assets.some(a => a.asset_id === id))) throw new Error('Ownership changed');
      }
      const key = 'dtos-trade-workspace:' + w.workspace_context.binding;
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null') || {};
      sessionStorage.setItem(key, JSON.stringify({...saved, schema: 2,
        currentProposal: {partner: proposal.partner_roster_id, sent: proposal.assets_sent, received: proposal.assets_received},
        originalProposal: null, previewProposal: null, adoptedProposal: null,
        originWorkflow: destination === 'calculator' && (proposal.assets_sent.includes(saved.requiredOutgoingAsset) || proposal.assets_received.includes(saved.requiredIncomingAsset)) ? saved.originWorkflow : 'create',
        requiredOutgoingAsset: destination === 'calculator' && proposal.assets_sent.includes(saved.requiredOutgoingAsset) ? saved.requiredOutgoingAsset : null,
        requiredIncomingAsset: destination === 'calculator' && proposal.assets_received.includes(saved.requiredIncomingAsset) ? saved.requiredIncomingAsset : null,
        ownership: w.workspace_context.ownership_generation}));
      location.assign('/trades/' + destination + '?front_office=' + proposal.active_roster_id);
    } catch (_) { button.textContent = 'Unable to open this proposal. Refresh the page and try again.'; button.disabled = false; }
  });
  const root = document.getElementById('trade-builder');
  if (!root) return;
  const el = id => document.getElementById(id), active = Number(root.dataset.frontOffice);
  const calculator = root.dataset.tradeWorkflow === 'calculator';
  const flow = calculator ? 'create' : root.dataset.tradeWorkflow.replace('-', '_');
  let workspace, revision = 0, runSequence = 0, side = 'sent', busy = false, entryBlocked = false, departed = false;
  let balanceRequest = null;
  let balanceFeedback = null;
  const balanceStatus = (text, offerRevision = revision, requestGeneration = runSequence) => {
    if (!calculator || offerRevision !== revision || requestGeneration !== runSequence) return;
    balanceFeedback = {text, offerRevision, requestGeneration};
    el('calculator-balance-status').textContent = balanceFeedback.text;
  };
  function clearStaleBalanceFeedback() {
    if (!balanceFeedback || (balanceFeedback.offerRevision === revision && balanceFeedback.requestGeneration === runSequence)) return;
    balanceFeedback = null; el('calculator-balance-status').textContent = '';
    if (lastOffersIsBalance) { lastOffers = null; lastOffersIsBalance = false; }
  }
  const clearBalancePreview = () => { if (session.previewProposal?.preview_balance_adjustment) session.previewProposal = null; };
  function cancelBalance() {
    if (!balanceRequest) return;
    balanceRequest.abort(); balanceRequest = null; revision++; runSequence++; busy = false;
    balanceStatus('Search cancelled. Your current offer is retained.');
  }
  // One account/session/league-bound state. Controls are views of these exact IDs.
  const session = {schema: 2, currentProposal: {sent: [], received: [], partner: 0}, originalProposal: null,
    previewProposal: null, adoptedProposal: null, requiredOutgoingAsset: null, requiredIncomingAsset: null,
    protectedAssets: [], excludedAssets: [], adjustmentConstraints: {}, originWorkflow: flow};
  const excludedFamilies = new Set(); let displayedFamilies = []; let lastOffers = null; let lastOffersIsBalance = false; let searchExhausted = false;
  const selected = session.currentProposal, filters = {sent: {q: '', pos: 'ALL'}, received: {q: '', pos: 'ALL'}};
  const team = id => workspace?.teams.find(t => t.roster_id === Number(id));
  const asset = id => workspace?.teams.flatMap(t => t.assets).find(a => a.asset_id === id);
  const label = a => a.raw_label || a.label;
  const partner = () => selected.partner;
  const setPartner = id => { selected.partner = Number(id); el('trade-partner').value = String(id); };
  const storageKey = () => 'dtos-trade-workspace:' + workspace.workspace_context.binding;
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
  function message(text, error = false) { const box = el('trade-result'); box.hidden = false; box.className = error ? 'tw-error' : ''; box.replaceChildren(node('p', text)); }
  function payload() { return {workflow: flow, strategy: el('trade-strategy').value || null, active_roster_id: active, partner_roster_id: partner(), assets_sent: [...selected.sent], assets_received: [...selected.received], protected_assets: [...session.protectedAssets], excluded_assets: [...session.excludedAssets], asset_id: flow === 'shop' ? session.requiredOutgoingAsset || selected.sent[0] : session.requiredIncomingAsset || selected.received[0], workspace_context: workspace.workspace_context}; }
  function persist() {
    if (departed) return;
    const draft = {...session, strategy: el('trade-strategy').value, ownership: workspace.workspace_context.ownership_generation};
    try { sessionStorage.setItem(storageKey(), JSON.stringify(draft)); } catch (_) { /* Storage-disabled browsing still works in this page. */ }
    // Each browser entry retains its own small draft, not search results. Only
    // reload/history may restore it, and only under fresh server authorization.
    try { history.replaceState({...history.state, dtosTrade: {
      binding: workspace.workspace_context.binding, workflow: flow,
      preload: root.dataset.preloadAsset, draft
    }}, ''); } catch (_) { /* History-disabled browsing still works. */ }
  }
  function restoredDraft() {
    if (departed) return null;
    const navigation = performance.getEntriesByType('navigation')[0]?.type;
    const entry = history.state?.dtosTrade;
    if (['reload', 'back_forward'].includes(navigation) && entry?.binding === workspace.workspace_context.binding &&
        entry.workflow === flow && entry.preload === root.dataset.preloadAsset) return entry.draft;
    return JSON.parse(sessionStorage.getItem(storageKey()) || 'null');
  }
  function syncLocks() { if (el('shop-protected')) for (const option of el('shop-protected').options) option.selected = session.protectedAssets.includes(option.value); }
  function addLock(kind, id) { if (!session[kind].includes(id)) session[kind].push(id); syncLocks(); persist(); }
  function changed() { cancelBalance(); const focusId = document.activeElement?.dataset.assetId; revision++; session.previewProposal = null; el('trade-result').hidden = true; persist(); paint(); if (focusId) root.querySelector('button[data-asset-id="' + CSS.escape(focusId) + '"]')?.focus(); }
  function toggle(which, id) { if (busy) return; const required = which === 'sent' ? session.requiredOutgoingAsset : session.requiredIncomingAsset; if (id === required && selected[which].includes(id)) return message('The required target stays fixed. Choose Build My Own to change the trade objective.', true); if (selected[which].includes(id)) selected[which] = selected[which].filter(x => x !== id); else if (!selected.sent.includes(id) && !selected.received.includes(id)) selected[which].push(id); changed(); }
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
    button.disabled = busy; button.setAttribute('aria-pressed', String(selected[which].includes(a.asset_id))); button.onclick = () => toggle(which, a.asset_id); row.append(button);
    if (a.kind === 'player') { const link = node('a', 'Dossier'); link.href = '/players/' + encodeURIComponent(a.asset_id.replace(/^player:/, '')); link.setAttribute('aria-label', 'Open ' + label(a) + ' player dossier'); row.append(link); }
    const evidence = marketEvidence(a); if (evidence) row.append(evidence);
    if (review) row.classList.add('tw-selected');
    return row;
  }
  function marketEvidence(a) {
    if (!a?.market_fact && a?.kind !== 'pick') return null;
    const details = node('details'); details.append(node('summary', 'Market evidence'));
    if (a.market_fact) {
      const f = a.market_fact;
      details.append(node('p', f.unavailability_reason || `${f.freshness} · ${f.evidence_coverage.join(', ')} · Evidence confidence ${f.confidence}/100`),
        node('small', `${f.fallback ? 'Last valid provider evidence · ' : ''}${f.source_updated_at ? 'Source as of ' + f.source_updated_at : 'Source timestamp unavailable'} · Retrieved ${f.retrieved_at || 'unavailable'}`),
        node('p', 'Source generation: ' + f.generation));
      details.dataset.marketGeneration = f.generation;
    } else {
      details.append(node('p', `Original franchise: ${a.original_roster_id} · Current owner: ${team(a.current_owner_id)?.team_name || 'Unavailable'} · Projected range: ${a.projected_range || 'Unknown'} · Range confidence: ${a.projected_range_confidence || 'Unavailable'}`));
      details.append(node('pre', JSON.stringify(a.pick_market_evidence || {availability: 'unavailable', reason: 'No supported pick Market evidence'}, null, 2)));
    }
    details.style.overflowWrap = 'anywhere'; details.style.minWidth = '0';
    return details;
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
    clearStaleBalanceFeedback();
    board('sent'); board('received');
    const targetBox = el('trade-target'), targetId = session.requiredIncomingAsset || session.requiredOutgoingAsset, target = asset(targetId);
    targetBox.replaceChildren(); targetBox.hidden = !target || entryBlocked;
    if (target && !entryBlocked) {
      targetBox.append(node('h3', session.requiredOutgoingAsset ? 'Asset you are shopping' : 'Player or pick you want'), identity(target));
      const owner = workspace.teams.find(t => t.assets.some(a => a.asset_id === targetId));
      const ownerLink = node('a', 'Current owner: ' + owner.team_name); ownerLink.href = '/teams/' + owner.roster_id; targetBox.append(ownerLink);
      if (target.kind === 'player') { const dossier = node('a', 'Open player dossier'); dossier.href = '/players/' + encodeURIComponent(target.asset_id.replace(/^player:/, '')); targetBox.append(dossier); }
    }
    for (const which of ['sent', 'received']) { const box = el('trade-' + which + '-chips'); box.replaceChildren(); for (const id of selected[which]) { const a = asset(id); if (a) box.append(assetRow(a, which, true)); else box.append(node('p', 'An asset is no longer available. Refresh this workspace.')); } }
    const count = selected.sent.length + selected.received.length;
    el('trade-tray').hidden = !count; el('trade-tray-text').textContent = `Trade proposal · ${count} assets · Send ${selected.sent.length} / Receive ${selected.received.length}`;
    const totals = which => { const rows = selected[which].map(asset); return rows.length && rows.every(a => a && a.trade_value != null) ? rows.reduce((sum, a) => sum + a.trade_value, 0) : null; };
    const sent = totals('sent'), received = totals('received'), balance = el('trade-balance'); balance.replaceChildren(node('h3', 'Market Balance'), node('p', `You send: ${sent ?? 'Unavailable'} · You receive: ${received ?? 'Unavailable'}`), node('small', 'Neutral market relationship only — not the Trade Intelligence recommendation.'));
    if (calculator) paintCalculator();
    el('trade-context').textContent = `${team(active)?.team_name || 'Your franchise'} → ${team(partner())?.team_name || 'Choose partner'} · Active league ${workspace.manager_context.league_id}`;
    el('trade-run').disabled = busy || !selected.sent.length || !selected.received.length;
    el('trade-find').disabled = busy || entryBlocked;
    el('trade-apply-adjust').disabled = busy;
    for (const id of ['trade-alternatives', 'calculator-lock', 'trade-release-lock']) if (el(id)) el(id).disabled = busy;
    if (calculator) {
      el('trade-balance-offer').textContent = balanceRequest ? 'Finding balancing options…' : 'Balance offer · preview options';
      el('trade-balance-offer').setAttribute('aria-busy', String(Boolean(balanceRequest)));
    }
    el('trade-build-own').disabled = busy && !balanceRequest;
    el('trade-build-own').hidden = flow === 'create' && !session.requiredOutgoingAsset && !session.requiredIncomingAsset;
    if (el('recommendation-refresh')) el('recommendation-refresh').disabled = busy || searchExhausted;
    // Keep the calculator live status outside a busy ancestor so assistive
    // technology announces processing immediately. Balance owns aria-busy.
    root.setAttribute('aria-busy', String(busy && !calculator));
  }
  function paintCalculator() {
    // Exact decimal arithmetic over the prepared canonical numbers, never
    // provider normalization, a fairness probability or strategic repricing.
    const rows = ['sent', 'received'].map(which => selected[which].map(asset));
    const parts = a => {
      const [digits, exponent = '0'] = String(a.trade_value).toLowerCase().split('e');
      const fraction = (digits.split('.')[1] || '').length;
      return {integer: BigInt(digits.replace('.', '')), scale: fraction - Number(exponent)};
    };
    const known = rows.flat().filter(a => a && typeof a.trade_value === 'number' && Number.isFinite(a.trade_value));
    const scale = Math.max(0, ...known.map(a => parts(a).scale));
    const units = a => { const p = parts(a); return p.integer * 10n ** BigInt(scale - p.scale); };
    const totals = rows.map(r => r.reduce((sum, a) => sum + (known.includes(a) ? units(a) : 0n), 0n));
    const shown = n => String(Number(n) / 10 ** scale);
    const complete = rows.every(r => r.length && r.every(a => known.includes(a)));
    const ownershipInvalid = ['sent', 'received'].some(which => selected[which].some(id => !team(which === 'sent' ? active : partner())?.assets.some(a => a.asset_id === id)));
    const box = el('trade-balance'); box.replaceChildren(node('h3', 'Canonical Market comparison'));
    rows.forEach((r, i) => box.append(node('p', `Side ${i ? 'B' : 'A'} · ${i ? 'You receive' : 'You send'}: ${r.length && r.every(a => known.includes(a)) ? shown(totals[i]) : r.some(a => known.includes(a)) ? 'Partial · known subtotal ' + shown(totals[i]) : 'Unavailable'}`)));
    const difference = totals[1] - totals[0];
    const verdict = node('h4', !complete ? rows.every(r => r.length) ? 'Cannot determine reliably · pricing evidence missing' : 'Choose assets on both sides' : difference === 0n ? 'Approximately balanced · equal canonical totals' : `Side ${difference > 0n ? 'A' : 'B'} favored · ${difference > 0n ? 'you receive more' : 'your counterparty receives more'} Market value`);
    verdict.id = 'calculator-verdict'; box.append(verdict);
    if (complete) box.append(node('p', 'Value gap: ' + shown(difference < 0n ? -difference : difference) + ' canonical Market points. This is an asset-price difference, not a guaranteed better trade.'));
    if (ownershipInvalid) box.append(node('p', 'Ownership invalid or unavailable: this retained hypothetical offer is not executable. Remove moved assets or select their current owner before balancing.', 'tw-error'));
    box.append(node('small', 'Market value ≠ lineup impact ≠ future capital ≠ strategy fit. Advanced DTOS analysis evaluates these separately.'));
    const locks = [...session.protectedAssets, ...session.excludedAssets];
    if (locks.length) box.append(node('p', 'Exact protections: ' + locks.map(id => label(asset(id) || {label: id})).join('; ')));
    if (selected.sent.some(id => session.protectedAssets.includes(id)) || [...selected.sent, ...selected.received].some(id => session.excludedAssets.includes(id))) box.append(node('p', 'Protected-asset conflict: remove the protected asset from this offer or explicitly release its lock.', 'tw-error'));
    for (const which of ['sent', 'received']) {
      const list = el('calculator-' + which); list.replaceChildren();
      if (!selected[which].length) list.append(node('p', 'No assets selected.'));
      for (const id of selected[which]) {
        const a = asset(id), row = node('div', null, 'tw-calculator-asset');
        const owner = workspace.teams.find(t => t.assets.some(item => item.asset_id === id));
        row.append(node('span', `${a ? label(a) : 'Ownership unavailable'} · ${a?.kind === 'pick' ? 'Pick' : 'Player'} · ${owner?.team_name || 'Owner unavailable'} · ${a?.trade_value ?? 'Market unavailable'}`));
        const remove = node('button', 'Remove'); remove.type = 'button'; remove.disabled = busy; remove.setAttribute('aria-label', 'Remove ' + (a ? label(a) : id) + ' from calculator'); remove.onclick = () => toggle(which, id); row.append(remove); list.append(row);
        const evidence = marketEvidence(a); if (evidence) list.append(evidence);
        if (which === 'received' && a) {
          const keep = node('button', session.requiredIncomingAsset === id ? 'Release incoming target' : 'Keep incoming target'); keep.type = 'button'; keep.disabled = busy; keep.onclick = () => { if (busy) return; session.requiredIncomingAsset = session.requiredIncomingAsset === id ? null : id; changed(); }; list.append(keep);
        }
      }
    }
    el('trade-balance-offer').disabled = busy || !complete || ownershipInvalid || difference === 0n;
  }
  function review() { el('trade-review').hidden = false; el('trade-board').hidden = true; el('trade-review').focus(); }
  function edit() { el('trade-board').hidden = false; el('trade-review').hidden = true; el('trade-assist').hidden = true; el('trade-partner').focus(); }
  async function post(path, requestPayload, signal) {
    const response = await fetch('/api/trades/' + path, {signal, method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': workspace.csrf_token}, body: JSON.stringify(requestPayload)});
    let body; try { body = await response.json(); } catch (_) { throw new Error("DTOS couldn't complete this evaluation. Your proposal is still intact."); }
    if (!response.ok) {
      const d = body.detail; const code = typeof d === 'string' ? d : d?.code || body.status;
      if (code === 'csrf_rejected' || code === 'authentication_required') throw new Error('Your secure session needs refreshing. Your proposal is still intact. Reload and sign in if needed.');
      if (code === 'workspace_context_changed' || code === 'unauthorized_league' || code === 'unauthorized_franchise') {
        const error = new Error('DTOS could not verify this workspace for your current session, league or franchise. Open Trade Center to load your authorized workspace. Your draft has not been submitted.');
        error.code = code; throw error;
      }
      if (code === 'canonical_evidence_changed') {
        const error = new Error('Market or projection evidence refreshed during this search. Your proposal and exact protections are unchanged. Try again when the refresh settles.');
        error.code = code; throw error;
      }
      throw new Error(d?.message || (typeof d === 'string' ? d : "DTOS couldn't complete this evaluation. Your proposal is still intact."));
    }
    return body;
  }
  function showEvaluation(e, opportunity = null) {
    const out = el('trade-result'); out.hidden = false; out.className = ''; out.replaceChildren();
    if (e.explanation_html) {
      // Same-origin server renderer escapes all evidence text. No client-side
      // recommendation/scoring or reason-code interpretation is performed.
      const document = new DOMParser().parseFromString(e.explanation_html, 'text/html');
      out.append(...document.body.childNodes);
      if (e.legality?.execution_status) out.append(node('p', e.legality.execution_status));
    } else {
    out.append(node('h3', e.recommendation || 'Assessment unavailable'), node('p', e.dominant_reason));
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
  function focusResult() { el('trade-result').focus(); }
  const newRecommendedObjective = row => (row.workflow || row.proposal.preview_origin_workflow) === 'recommended' && session.originWorkflow !== 'recommended';
  function offerConflict(row) {
    const p = row.proposal;
    if (p.assets_sent.some(id => session.protectedAssets.includes(id) || session.excludedAssets.includes(id)) || p.assets_received.some(id => session.excludedAssets.includes(id))) return 'This offer violates an exact asset lock. Your proposal is unchanged.';
    if (!newRecommendedObjective(row)) {
      if ((session.requiredOutgoingAsset && !p.assets_sent.includes(session.requiredOutgoingAsset)) || (session.requiredIncomingAsset && !p.assets_received.includes(session.requiredIncomingAsset))) return 'This offer removes the required trade target. Your proposal is unchanged.';
      if (session.requiredIncomingAsset && !team(p.partner_roster_id)?.assets.some(a => a.asset_id === session.requiredIncomingAsset)) return 'The required target belongs to a different owner. Your proposal is unchanged.';
    }
    return null;
  }
  function openOffer(row) {
    const conflict = offerConflict(row); if (conflict) return message(conflict, true);
    if (newRecommendedObjective(row)) { session.requiredOutgoingAsset = null; session.requiredIncomingAsset = null; session.originWorkflow = 'recommended'; }
    setPartner(row.proposal.partner_roster_id); selected.sent = [...row.proposal.assets_sent]; selected.received = [...row.proposal.assets_received];
    session.adoptedProposal = {...selected, sent: [...selected.sent], received: [...selected.received]};
    changed(); review(); showEvaluation(row.evaluation || row.proposal.preview_assessment || {}, row.opportunity); focusResult();
  }
  function previewOffer(row) {
    const conflict = offerConflict(row); if (conflict) return message(conflict, true);
    const adjustment = row.balance_adjustment || row.proposal.preview_balance_adjustment;
    if (adjustment && adjustment.market_generation !== workspace.calculator_generation) {
      session.previewProposal = null; persist();
      return message('Market evidence updated. Your current offer and protections are retained; balance again to preview current totals.', true);
    }
    const original = {sent: [...selected.sent], received: [...selected.received], partner: partner()};
    const summary = row.evaluation ? Object.fromEntries(['recommendation', 'dominant_reason', 'why_you_would_do_it', 'major_drawback', 'counterparty_summary', 'why_they_would_do_it'].filter(key => typeof row.evaluation[key] === 'string').map(key => [key, row.evaluation[key].slice(0, 1200)])) : row.proposal.preview_assessment;
    session.originalProposal = original; session.previewProposal = {...row.proposal, preview_assessment: summary, preview_balance_adjustment: row.balance_adjustment || row.proposal.preview_balance_adjustment, preview_origin_workflow: row.workflow || row.proposal.preview_origin_workflow || session.originWorkflow}; persist();
    const out = el('trade-result'); out.hidden = false; out.replaceChildren(node('h3', 'Alternative preview'));
    const names = ids => ids.map(id => label(asset(id) || {label: id})).join(' + ') || 'None';
    out.append(node('p', 'Original: ' + names(original.sent) + ' → ' + names(original.received)),
      node('p', 'Alternative: ' + names(row.proposal.assets_sent) + ' → ' + names(row.proposal.assets_received)));
    const cost = ids => ids.every(id => asset(id)?.trade_value != null) ? ids.reduce((sum, id) => sum + asset(id).trade_value, 0) : null;
    const oldCost = cost(original.sent), newCost = cost(row.proposal.assets_sent);
    if (original.sent.length && oldCost != null && newCost != null) out.append(node('p', 'Outgoing Market cost: ' + oldCost + ' → ' + newCost));
    if (adjustment) {
      for (const [heading, m] of [['Original', adjustment.original], ['Suggested', adjustment.suggested]]) out.append(node('p', `${heading} Market: ${m.sent.total} sent / ${m.received.total} received · Gap ${m.absolute_gap}`));
      out.append(node('p', adjustment.reason), node('small', adjustment.meaning));
    }
    out.append(offerCard(row, true));
    const adopt = node('button', 'Adopt alternative'); adopt.type = 'button'; adopt.onclick = () => openOffer(row);
    const keep = node('button', 'Keep original'); keep.type = 'button'; keep.disabled = busy; keep.onclick = () => { session.previewProposal = null; persist(); if (lastOffers) offers(lastOffers, lastOffersIsBalance); else message('Original proposal kept.'); };
    out.append(adopt, keep); focusResult();
  }
  function offerCard(row, preview = false) {
    const card = node('article', null, 'tw-offer');
    const e = row.evaluation || row.proposal.preview_assessment || {};
    const balance = row.balance_adjustment || row.proposal.preview_balance_adjustment;
    card.append(node('h3', balance ? 'Market adjustment · preview' : e.recommendation || 'Recommendation unavailable'));
    if (balance) card.append(node('p', balance.change.replaceAll('_', ' ') + ` · Gap ${balance.original.absolute_gap} → ${balance.suggested.absolute_gap}`), node('p', 'Separate DTOS assessment: ' + (e.recommendation || 'Unavailable')), node('small', balance.strategic_caution ? 'Market balance improves; roster, strategy or counterparty evidence raises a caution. Review the major drawback.' : balance.meaning));
    if (row.repair_type) card.append(node('p', row.repair_type));
    if (row.adjustment_evidence?.concept === 'strictly_lower_canonical_outgoing_market_cost') {
      const cost = row.adjustment_evidence;
      card.append(node('p', `Outgoing Market cost: ${cost.current_outgoing_cost} → ${cost.alternative_outgoing_cost} (${cost.market_cost_reduction} lower).`));
    }
    card.append(node('p', (row.proposal_presentation?.send || []).map(a => a.label).join(' + ') + ' → ' + (row.proposal_presentation?.receive || []).map(a => a.label).join(' + ')),
      node('p', 'Why this helps me: ' + (e.why_you_would_do_it || e.dominant_reason || 'Review the supported evidence.')),
      node('p', 'Major drawback: ' + (e.major_drawback || e.major_risks?.join('; ').replaceAll('_', ' ') || e.major_limitations?.join('; ').replaceAll('_', ' ') || 'No material drawback identified in available evidence.')),
      node('p', 'Counterparty: ' + (e.counterparty_summary || e.why_they_would_do_it || e.dimensions?.counterparty_plausibility?.explanation || 'Review the separate bilateral evidence.')));
    const intent = e.dimensions?.strategic_fit?.active?.manager_strategy?.strategy;
    if (intent) card.append(node('p', 'Strategy: ' + intent));
    const history = e.dimensions?.counterparty_plausibility?.manager_history?.disclosure;
    if (history) card.append(node('small', history));
    if (!preview) { const b = node('button', balance ? 'Preview adjustment' : 'Open editable offer: preview'); b.type = 'button'; b.onclick = () => previewOffer(row); card.append(b); }
    if (e.explanation_html) {
      const detail = node('details'); detail.append(node('summary', 'Why this offer · evidence and risks'));
      const parsed = new DOMParser().parseFromString(e.explanation_html, 'text/html');
      detail.append(...parsed.body.childNodes); card.append(detail);
    }
    if (row.variants?.length && !preview) {
      const detail = node('details'); detail.append(node('summary', 'Related package variants'));
      for (const variant of row.variants) detail.append(offerCard(variant)); card.append(detail);
    }
    return card;
  }
  function searchDetails(body, out) {
    const assessedBlocker = body.near_misses?.find(row => row.proposal && row.evaluation && (row.blocking_asset_ids?.length || row.conflict_explanation));
    const blocker = body.blocking_asset_ids?.length || body.conflict_explanation || body.smallest_optional_relaxation ? body : assessedBlocker;
    if (blocker) {
      const conflict = node('section', null, 'tw-conflict');
      conflict.append(node('h4', blocker === body ? 'Exact constraint conflict' : 'Evaluated package blocker'));
      for (const id of blocker.blocking_asset_ids || []) conflict.append(node('p', 'Blocking asset: ' + label(asset(id) || {label: id}) + ' · ' + id));
      if (blocker.conflict_explanation) conflict.append(node('p', blocker.conflict_explanation));
      else if (blocker.blocking_asset_ids?.length) conflict.append(node('p', 'These exact locks conflict with the required trade objective.'));
      if (blocker.smallest_optional_relaxation) conflict.append(node('p', 'Optional change: ' + blocker.smallest_optional_relaxation));
      conflict.append(node('small', 'Your locks and original proposal remain unchanged.'));
      out.append(conflict);
    }
    if (body.near_misses?.length) {
      const detail = node('details'); detail.append(node('summary', 'Evaluated near misses'));
      for (const row of body.near_misses) {
        const p = row.proposal;
        if (!p || !row.evaluation) continue; // A near miss must be an assessed package.
        const names = (presented, ids) => presented?.length ? presented.map(a => a.label).join(' + ') : (ids || []).map(id => label(asset(id) || {label: id})).join(' + ');
        detail.append(node('p', names(row.proposal_presentation?.send, p.assets_sent) + ' → ' + names(row.proposal_presentation?.receive, p.assets_received)),
          node('p', row.conflict_explanation || row.blocker_type + ': ' + (row.blockers || []).join(', ').replaceAll('_', ' ')));
        for (const id of row.blocking_asset_ids || []) detail.append(node('p', 'Blocking asset: ' + label(asset(id) || {label: id}) + ' · ' + id));
        if (row.smallest_optional_relaxation) detail.append(node('p', 'Optional change: ' + row.smallest_optional_relaxation));
      }
      out.append(detail);
    }
    if (body.search_evidence) { const detail = node('details'); detail.append(node('summary', 'Technical search details'), node('pre', JSON.stringify(body.search_evidence, null, 2))); out.append(detail); }
  }
  function offers(body, isBalance = false) {
    lastOffers = body; lastOffersIsBalance = isBalance;
    if (flow === 'recommended' && body.workflow === 'recommended') {
      displayedFamilies = (body.results || []).map(row => row.family_id);
      searchExhausted = body.has_more === false;
      const out = el('trade-result'); out.hidden = false; out.replaceChildren();
      if (!body.results?.length) out.append(node('p', body.quiet_state || 'No credible opportunity.'));
      for (const row of body.results || []) {
        out.append(offerCard(row));
      }
      for (const reason of body.discovery?.limitations || []) out.append(node('small', reason.replaceAll('_', ' ')));
      searchDetails(body, out);
      return;
    }
    if (flow === 'shop' && body.markets) {
      const out = el('trade-result'); out.hidden = false; out.replaceChildren();
      if (!body.markets.length) out.append(node('p', body.quiet_state || 'No credible market in this bounded search.'));
      for (const limitation of body.shop_preference?.limitations || []) out.append(node('p', limitation));
      for (const market of body.markets) {
        out.append(node('h3', team(market.counterparty_roster_id)?.team_name || 'Counterparty'),
          node('p', market.buyer_rationale?.explanation || 'Review the shared counterparty evidence.'));
        for (const row of market.returns) out.append(offerCard(row));
      }
      searchDetails(body, out);
      return;
    }
    if (!body.results?.length) { message(body.conflict_explanation || body.quiet_state || 'No credible adjustment found. Your proposal is unchanged.'); searchDetails(body, el('trade-result')); return; }
    const out = el('trade-result'); out.hidden = false; out.replaceChildren();
    for (const row of body.results) out.append(offerCard(row));
    searchDetails(body, out);
  }
  async function run(path, extra = {}) {
    if (busy || !workspace) return;
    if (path === 'generate' && entryBlocked) return;
    if (path === 'generate' && ((flow === 'shop' && !session.requiredOutgoingAsset && selected.sent.length !== 1) || (flow === 'trade_for' && !session.requiredIncomingAsset && selected.received.length !== 1))) return message('Choose one target asset for this search. Multi-asset proposals can still be evaluated directly.', true);
    if (path === 'generate' && flow === 'shop') {
      session.requiredOutgoingAsset = session.requiredOutgoingAsset || selected.sent[0]; session.requiredIncomingAsset = null; session.originWorkflow = 'shop';
      extra = {...extra, partner_roster_id: partner(), asset_id: session.requiredOutgoingAsset,
        shop_preference: el('shop-preference').value,
        shop_position: el('shop-preference').value === 'position_need' ? el('shop-position').value : null};
    }
    if (path === 'generate' && flow === 'trade_for') { session.requiredIncomingAsset = session.requiredIncomingAsset || selected.received[0]; session.requiredOutgoingAsset = null; session.originWorkflow = 'trade_for'; }
    if (path === 'generate' && flow === 'recommended') extra = {...extra, partner_roster_id: 0, asset_id: null,
      recommendation_filter: el('recommendation-filter').value, excluded_recommendation_families: [...excludedFamilies]};
    if (path === 'assist' || path === 'alternatives') {
      extra.origin_workflow = session.originWorkflow;
      const instruction = (extra.instruction || '').toLowerCase();
      const exact = extra.constraint_asset_id;
      if (exact && /^(keep|protect|do not trade|don't trade)/.test(instruction)) addLock('protectedAssets', exact);
      if (exact && /^(replace|exclude)/.test(instruction)) addLock('excludedAssets', exact);
      if (session.requiredOutgoingAsset) extra.origin_asset_id = session.requiredOutgoingAsset;
      const text = (extra.instruction || '').trim().toLowerCase();
      extra.repair_mode = text === 'alternative target' ? 'ALTERNATIVE_TARGET' : text === 'alternative construction' ? 'ALTERNATIVE_CONSTRUCTION' : 'MAKE_THIS_TRADE_WORK';
      session.adjustmentConstraints = {instruction: extra.instruction || '', constraint_asset_id: exact || null, repair_mode: extra.repair_mode};
    }
    if (path === 'balance') extra = {...extra, market_generation: workspace.calculator_generation, required_outgoing_asset: session.requiredOutgoingAsset, required_incoming_asset: session.requiredIncomingAsset};
    session.previewProposal = null; persist();
    busy = true; const started = revision, startedRun = ++runSequence;
    const controller = path === 'balance' ? new AbortController() : null;
    let timedOut = false;
    const timeout = controller ? setTimeout(() => { timedOut = true; controller.abort(); }, 45000) : null;
    if (controller) { balanceRequest = controller; balanceStatus('Finding balancing options… Asset changes pause until this search finishes. Your offer stays intact.'); }
    // Freeze the exact request, including binding, anchors and locks. A retry
    // must never reinterpret it under a newer navigation or strategy intent.
    const requestPayload = {...payload(), ...extra}; paint();
    message(path === 'balance' ? 'Checking owned, lock-respecting Market adjustments… Your original stays intact.' : path === 'generate' ? 'Searching supported bilateral options… Your proposal stays intact.' : path === 'assist' ? 'Checking revised offers… Your original proposal stays intact.' : 'Evaluating your proposal…');
    try {
      let body;
      try { body = await post(path, requestPayload, controller?.signal); } catch (error) {
        if (error.code !== 'canonical_evidence_changed' || started !== revision) throw error;
        message('Evidence refreshed. Checking the same request once more… Your proposal stays intact.');
        body = await post(path, requestPayload, controller?.signal);
      }
      if (started !== revision) return;
      for (const id of body.constraints?.protected_assets || []) addLock('protectedAssets', id);
      for (const id of body.constraints?.excluded_assets || []) addLock('excludedAssets', id);
      if (path === 'assist') {
        const lostTarget = body.results?.some(row => selected.received.some(id => !row.proposal.assets_received.includes(id)));
        const youngerChange = (extra.instruction || '').toLowerCase().includes('younger') && !['shop', 'trade_for'].includes(session.originWorkflow);
        const invalidPreservation = body.results?.length && !youngerChange && extra.repair_mode !== 'ALTERNATIVE_TARGET' && (body.target_preserved !== true || lostTarget);
        if (body.requested_mode !== extra.repair_mode || body.returned_modes?.some(mode => mode !== extra.repair_mode) || invalidPreservation) throw new Error('DTOS rejected a mismatched repair mode. Your proposal is unchanged.');
      }
      if (path === 'balance') balanceStatus(body.results?.length ? 'Balancing options ready. Preview before adopting.' : 'No balancing options returned. Your offer is unchanged.', started, startedRun);
      if (path === 'evaluate') { review(); showEvaluation(body.evaluation); } else offers(body, path === 'balance');
    } catch (error) { if (started === revision) {
      const feedback = timedOut ? 'Balancing timed out. Your offer is unchanged. Try again.' : path === 'balance' && error instanceof TypeError ? 'Balancing could not connect. Your offer is unchanged. Try again.' : error.message;
      if (path === 'balance') balanceStatus(feedback, started, startedRun);
      message(feedback, true);
      if (path === 'balance' && error.code === 'canonical_evidence_changed') {
        message('Market evidence changed. Your offer and exact protections are intact. Reload Market facts before balancing.', true);
        const reload = node('button', 'Reload Market facts'); reload.type = 'button'; reload.onclick = () => location.reload();
        el('trade-result').append(reload);
      }
      if (['workspace_context_changed', 'unauthorized_league', 'unauthorized_franchise'].includes(error.code)) {
        const link = node('a', 'Open current Trade Center'); link.href = '/trades';
        el('trade-result').append(link);
      }
    } } finally {
      if (timeout !== null) clearTimeout(timeout);
      if (startedRun === runSequence) {
        if (balanceRequest === controller) balanceRequest = null;
        busy = false; paint();
        if (started === revision && !el('trade-result').hidden) focusResult();
      }
    }
  }
  el('trade-view').onclick = review; el('trade-tray-view').onclick = review; el('trade-edit').onclick = edit;
  el('trade-run').onclick = () => run('evaluate'); el('trade-find').onclick = () => run('generate');
  if (calculator) {
    el('trade-balance-offer').onclick = () => run('balance');
    el('calculator-protect').onclick = () => { el('trade-assist').hidden = false; el('trade-constraint-asset').focus(); };
    el('calculator-lock').onclick = () => { if (busy) return; const exact = el('trade-constraint-asset').value; if (!exact) return message('Choose an exact owned player or pick to protect.', true); addLock('protectedAssets', exact); revision++; clearBalancePreview(); persist(); paint(); message('Exact outgoing protection added. Original offer retained; remove this asset if it is currently outgoing.'); };
  }
  el('trade-build-own').onclick = () => {
    if (!workspace) return;
    cancelBalance(); if (busy) return;
    session.requiredOutgoingAsset = null; session.requiredIncomingAsset = null; session.originWorkflow = 'create';
    selected.sent = []; selected.received = []; setPartner(0);
    session.originalProposal = null; session.adoptedProposal = null; session.previewProposal = null; persist();
    location.assign('/trades/create?front_office=' + active);
  };
  el('trade-adjust').onclick = () => { el('trade-assist').hidden = false; el('trade-instruction').focus(); };
  el('trade-apply-adjust').onclick = () => run('assist', {instruction: el('trade-instruction').value || 'make this trade work', constraint_asset_id: el('trade-constraint-asset').value || null});
  const saveAdjustment = () => { session.adjustmentConstraints = {...session.adjustmentConstraints, instruction: el('trade-instruction').value, constraint_asset_id: el('trade-constraint-asset').value || null}; persist(); };
  el('trade-instruction').oninput = saveAdjustment; el('trade-constraint-asset').onchange = saveAdjustment;
  el('trade-alternatives').onclick = () => run('alternatives');
  el('trade-release-lock').onclick = () => {
    if (busy) return;
    const exact = el('trade-constraint-asset').value;
    if (!exact) return message('Choose the exact adjustment lock to remove.', true);
    session.protectedAssets = session.protectedAssets.filter(id => id !== exact); session.excludedAssets = session.excludedAssets.filter(id => id !== exact); syncLocks(); revision++; clearBalancePreview(); persist(); paint();
    message('Adjustment lock removed for ' + label(asset(exact)) + '. Original proposal kept.');
  };
  root.querySelectorAll('[data-adjust]').forEach(b => b.onclick = () => {
    const exact = asset(el('trade-constraint-asset').value), instruction = b.dataset.adjust;
    if ((instruction.includes('this pick') && exact?.kind !== 'pick') || (instruction.includes('this player') && exact?.kind !== 'player') || (instruction.includes('this asset') && !exact)) return message('Choose the specific owned player or pick first.', true);
    el('trade-instruction').value = instruction;
    saveAdjustment();
  });
  root.querySelectorAll('[data-side]').forEach(b => b.onclick = () => { side = b.dataset.side; root.querySelectorAll('[data-side]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); paint(); });
  el('trade-partner').onchange = () => { if (session.requiredIncomingAsset) { el('trade-partner').value = String(partner()); return message('The required target stays with its actual owner. Choose Build My Own to change the objective.', true); } setPartner(el('trade-partner').value); selected.received = []; changed(); };
  el('trade-strategy').onchange = () => { cancelBalance(); revision++; clearBalancePreview(); if (workspace) paint(); excludedFamilies.clear(); searchExhausted = false; el('trade-result').hidden = true; persist(); };
  // A document restored from browser history must not accept a response from
  // work started before leaving it. Normal navigation loads fresh server context.
  addEventListener('pagehide', () => {
    cancelBalance(); departed = true; revision++; runSequence++;
    busy = false; el('trade-result').hidden = true; if (workspace) paint();
  });
  addEventListener('pageshow', event => {
    // BF-cache keeps this document's own proposal and locks. Make it the active
    // draft again; a later explicit action must start from this history entry.
    if (event.persisted) {
      departed = false;
      if (workspace && history.state?.dtosTrade?.binding === workspace.workspace_context.binding) persist();
    }
  });
  matchMedia('(max-width:760px)').addEventListener('change', () => { if (workspace) paint(); });
  fetch('/api/trades/workspace?front_office=' + active + (calculator ? '&mode=calculator' : ''), {credentials: 'same-origin'}).then(async response => { if (!response.ok) throw new Error('Unable to load this authorized workspace.'); return response.json(); }).then(data => {
    workspace = data;
    for (const a of team(active)?.assets || []) { const option = node('option', label(a) + (a.kind === 'pick' ? ' · Original franchise ' + a.original_roster_id + ' · ' + a.asset_id : '')); option.value = a.asset_id; el('trade-constraint-asset').append(option); }
    if (flow === 'recommended') {
      el('trade-find').textContent = 'Discover Recommended Trades';
      el('recommendation-refresh').onclick = () => {
        if (busy) return;
        for (const family of displayedFamilies) if (excludedFamilies.size < 256) excludedFamilies.add(family);
        run('generate');
      };
      el('recommendation-filter').onchange = () => { excludedFamilies.clear(); searchExhausted = false; revision++; el('trade-result').hidden = true; };
    }
    if (flow === 'shop') {
      for (const a of team(active)?.assets || []) { const option = node('option', label(a)); option.value = a.asset_id; el('shop-protected').append(option); }
      el('shop-preference').onchange = () => { el('shop-position').disabled = el('shop-preference').value !== 'position_need'; revision++; el('trade-result').hidden = true; };
      el('shop-position').onchange = () => { revision++; el('trade-result').hidden = true; };
      el('shop-protected').onchange = () => { session.protectedAssets = Array.from(el('shop-protected').selectedOptions, option => option.value); revision++; session.previewProposal = null; el('trade-result').hidden = true; persist(); };
    }
    if (!departed) try { for (const key of Object.keys(sessionStorage)) if (key.startsWith('dtos-trade-workspace:') && key !== storageKey()) sessionStorage.removeItem(key); } catch (_) { /* Storage is optional. */ }
    for (const t of data.teams) if (t.roster_id !== active) { const option = node('option', t.team_name); option.value = t.roster_id; el('trade-partner').append(option); }
    try {
      const saved = restoredDraft();
      const proposal = saved?.currentProposal || (saved?.selected ? {...saved.selected, partner: saved.partner} : null);
      if (proposal && (team(proposal.partner) || Number(proposal.partner) === 0) && Array.isArray(proposal.sent) && Array.isArray(proposal.received)) {
        setPartner(proposal.partner); selected.sent = [...proposal.sent]; selected.received = [...proposal.received];
        for (const key of ['originalProposal', 'previewProposal', 'adoptedProposal', 'requiredOutgoingAsset', 'requiredIncomingAsset', 'adjustmentConstraints', 'originWorkflow']) if (saved.schema === 2 && key in saved) session[key] = saved[key];
        for (const key of ['protectedAssets', 'excludedAssets']) if (Array.isArray(saved[key])) session[key] = [...new Set(saved[key])];
        if (saved.strategy && Array.from(el('trade-strategy').options).some(o => o.value === saved.strategy)) el('trade-strategy').value = saved.strategy;
        if (saved.ownership !== data.workspace_context.ownership_generation) message('Ownership has changed. Your proposal is retained for review; evaluation will identify any assets that moved.', true);
      }
    } catch (_) { /* No persisted draft is required. */ }
    const preload = root.dataset.preloadAsset;
    if (preload) {
      const owner = data.teams.find(t => t.assets.some(a => a.asset_id === preload));
      if (!owner || (flow === 'shop' && owner.roster_id !== active) || (flow === 'trade_for' && owner.roster_id === active)) {
        entryBlocked = true; message('This asset is not currently owned by the required franchise. Review current ownership or choose another Trade Center entry.', true);
      } else {
        const compatible = session.originWorkflow === flow && (flow === 'shop'
          ? session.requiredOutgoingAsset === preload && !session.requiredIncomingAsset && selected.sent.includes(preload)
          : session.requiredIncomingAsset === preload && !session.requiredOutgoingAsset && selected.received.includes(preload));
        if (!compatible) {
          const replaced = selected.sent.length || selected.received.length;
          // Explicit entry targets outrank unrelated restored intent. Exact
          // locks survive within this authorized binding and remain enforced.
          revision++;
          selected.sent = []; selected.received = []; setPartner(0);
          session.originalProposal = null; session.previewProposal = null; session.adoptedProposal = null;
          session.adjustmentConstraints = {}; session.originWorkflow = flow;
          session.requiredOutgoingAsset = flow === 'shop' ? preload : null;
          session.requiredIncomingAsset = flow === 'trade_for' ? preload : null;
          if (flow === 'shop') selected.sent = [preload];
          else { setPartner(owner.roster_id); selected.received = [preload]; }
          if (replaced) message((flow === 'shop' ? 'Now shopping ' : 'Now pursuing ') + label(asset(preload)) + '. The previous package was cleared. Exact protections are retained.');
        } else if (flow === 'trade_for') setPartner(owner.roster_id);
      }
    }
    el('trade-instruction').value = session.adjustmentConstraints.instruction || '';
    el('trade-constraint-asset').value = session.adjustmentConstraints.constraint_asset_id || '';
    syncLocks(); el('trade-find').hidden = flow === 'create'; persist(); paint();
    if (session.previewProposal && !entryBlocked) previewOffer({proposal: session.previewProposal});
  }).catch(error => message(error.message, true));
})();
