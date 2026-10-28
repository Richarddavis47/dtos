/* One temporary, account/session/league-bound proposal. No external execution. */
(() => {
  'use strict';
  function tradeTabOwner() {
    // sessionStorage can be cloned by window.open. A non-secret per-window
    // marker separates editable drafts without sharing assets between tabs.
    const match = window.name.match(/\|dtos-trade-tab=([a-zA-Z0-9-]+)$/);
    if (match) return match[1];
    const value = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
    window.name += '|dtos-trade-tab=' + value;
    return value;
  }
  // Home ends only this tab's authorized league workflow. Strategy lives in
  // its separate session cookie; other tabs/leagues and supporting routes stay intact.
  const homeBoundary = document.getElementById('trade-home-boundary');
  if (homeBoundary) {
    const endWorkflow = () => {
      try {
        const context = JSON.parse(homeBoundary.dataset.workspaceContext);
        if (!context.binding) return;
        const key = 'dtos-trade-workspace:' + context.binding;
        const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
        if (saved && !saved.endedAtHome) sessionStorage.setItem(key, JSON.stringify({...saved,
          endedAtHome: true, resetGeneration: String(Date.now()) + ':' + Math.random().toString(36).slice(2)}));
      } catch (_) { /* Storage-disabled browsing does not affect server authority. */ }
    };
    endWorkflow(); addEventListener('pageshow', endWorkflow);
  }
  // Presentation only: retain canonical precision and unavailable evidence.
  function displayPoints(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return 'Unavailable';
    const displayed = value.toFixed(2);
    return displayed === '-0.00' ? '0.00' : displayed;
  }
  // Derived Market totals only. Individual projections use the canonical
  // player/week display supplied by the server, never this formatter.
  function marketParts(value) {
    const [digits, exponent = '0'] = String(value).toLowerCase().split('e');
    return {integer: BigInt(digits.replace('.', '')), scale: (digits.split('.')[1] || '').length - Number(exponent)};
  }
  function displayMarketUnits(integer, scale) {
    // Match canonical manager_points (decimal half-even) when a prepared display
    // is absent. Keep exact arithmetic; never round individual projections.
    const negative = integer < 0n, magnitude = negative ? -integer : integer;
    let cents;
    if (scale > 2) {
      const divisor = 10n ** BigInt(scale - 2), quotient = magnitude / divisor, remainder = magnitude % divisor;
      cents = quotient + (remainder * 2n > divisor || remainder * 2n === divisor && quotient % 2n === 1n ? 1n : 0n);
    } else cents = magnitude * 10n ** BigInt(2 - scale);
    const fraction = String(cents % 100n).padStart(2, '0').replace(/0+$/, '');
    return (negative && cents ? '-' : '') + String(cents / 100n) + (fraction ? '.' + fraction : '');
  }
  function displayMarket(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return 'Unavailable';
    const parts = marketParts(value);
    return displayMarketUnits(parts.integer, parts.scale);
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
      const retained = JSON.parse(sessionStorage.getItem(key) || 'null');
      const owner = tradeTabOwner();
      // A new explicit offer supersedes an ended or other-tab draft; its old
      // objective and proposal-specific constraints must not follow the import.
      const saved = retained && !retained.endedAtHome && (!retained.tabOwner || retained.tabOwner === owner) ? retained : {};
      sessionStorage.setItem(key, JSON.stringify({...saved, schema: 2, tabOwner: owner, endedAtHome: false,
        resetGeneration: String(Date.now()) + ':' + Math.random().toString(36).slice(2),
        currentProposal: {partner: proposal.partner_roster_id, sent: proposal.assets_sent, received: proposal.assets_received},
        originalProposal: null, previewProposal: null, adoptedProposal: null, currentAssessment: null,
        originWorkflow: destination === 'calculator' && (proposal.assets_sent.includes(saved.requiredOutgoingAsset) || proposal.assets_received.includes(saved.requiredIncomingAsset)) ? saved.originWorkflow : 'create',
        requiredOutgoingAsset: destination === 'calculator' && proposal.assets_sent.includes(saved.requiredOutgoingAsset) ? saved.requiredOutgoingAsset : null,
        requiredIncomingAsset: destination === 'calculator' && proposal.assets_received.includes(saved.requiredIncomingAsset) ? saved.requiredIncomingAsset : null,
        ownership: w.workspace_context.ownership_generation}));
      location.assign('/trades/' + destination + '?front_office=' + proposal.active_roster_id);
    } catch (_) { button.textContent = 'Unable to open this proposal. Refresh the page and try again.'; button.disabled = false; }
  });
  const root = document.getElementById('trade-builder');
  if (!root) return;
  const tabOwner = tradeTabOwner();
  const el = id => document.getElementById(id), active = Number(root.dataset.frontOffice);
  const calculator = root.dataset.tradeWorkflow === 'calculator';
  const marketEditor = calculator || root.dataset.tradeWorkflow === 'create';
  const flow = calculator ? 'create' : root.dataset.tradeWorkflow.replace('-', '_');
  let workspace, revision = 0, runSequence = 0, side = root.dataset.tradeWorkflow === 'trade-for' ? 'received' : 'sent', busy = false, entryBlocked = false, departed = false;
  let balanceRequest = null, activeRequest = null;
  let balanceFeedback = null;
  let searchFeedback = null;
  function searchStatus(text, state, offerRevision = revision, requestGeneration = runSequence) {
    if (!el('recommendation-status') || offerRevision !== revision || requestGeneration !== runSequence) return;
    searchFeedback = {text, state, offerRevision, requestGeneration};
    el('recommendation-status').dataset.searchState = state;
    el('recommendation-status').textContent = text; el('recommendation-status').dataset.state = state;
  }
  const balanceStatus = (text, offerRevision = revision, requestGeneration = runSequence) => {
    if (offerRevision !== revision || requestGeneration !== runSequence) return;
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
    if (!activeRequest) return;
    activeRequest.abort(); activeRequest = null; balanceRequest = null; revision++; runSequence++; busy = false;
    balanceStatus('Search cancelled. Your current offer is retained.');
  }
  // One account/session/league-bound state. Controls are views of these exact IDs.
  const session = {schema: 2, resetGeneration: null, currentProposal: {sent: [], received: [], partner: 0}, originalProposal: null,
    previewProposal: null, adoptedProposal: null, requiredOutgoingAsset: null, requiredIncomingAsset: null,
    protectedAssets: [], excludedAssets: [], overrideSavedProtections: [], adjustmentConstraints: {}, originWorkflow: flow, shopSearchPartner: 0,
    shopScopeAsset: null, shopPreference: 'best_overall', shopPosition: 'QB', currentAssessment: null};
  const excludedFamilies = new Set(); let displayedFamilies = []; let lastOffers = null; let lastOffersIsBalance = false; let searchExhausted = false;
  let valuationMode = 'neutral', personalRevisionStale = false, checkingPersonal = false;
  const latestEvidence = {};
  const sourceKeys = ['market_generation', 'projection_generation', 'historical_generation'];
  const selected = session.currentProposal, filters = {sent: {q: '', pos: 'ALL'}, received: {q: '', pos: 'ALL'}};
  const team = id => workspace?.teams.find(t => t.roster_id === Number(id));
  const asset = id => workspace?.teams.flatMap(t => t.assets).find(a => a.asset_id === id);
  const label = a => a.raw_label || a.label;
  const partner = () => selected.partner;
  const setPartner = id => { selected.partner = Number(id); el('trade-partner').value = flow === 'shop' ? (session.shopSearchPartner ? String(session.shopSearchPartner) : '') : Number(id) ? String(id) : ''; };
  const storageKey = () => 'dtos-trade-workspace:' + workspace.workspace_context.binding;
  const node = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
  el('trade-result').dataset.assessmentState = 'not_evaluated';
  function message(text, error = false) { const box = el('trade-result'); delete box.dataset.assessment; delete box.dataset.assessmentFreshness; box.dataset.assessmentState = 'not_evaluated'; box.hidden = false; box.className = error ? 'tw-error' : ''; box.replaceChildren(node('p', text)); }
  function personalChangedNotice() {
    message('Saved personal rankings, permissions or source evidence changed. Your exact draft is retained; reload current facts before evaluating or searching.', true);
    const reload = node('button', 'Reload current facts'); reload.type = 'button'; reload.onclick = () => location.reload();
    el('trade-result').append(reload);
  }
  async function checkPersonalRevision() {
    if (!workspace?.personalization || checkingPersonal || departed || document.hidden) return;
    checkingPersonal = true;
    const binding = workspace.workspace_context.binding;
    try {
      const response = await fetch('/api/my-dtos', {credentials: 'same-origin', cache: 'no-store'});
      const state = response.ok ? await response.json() : null;
      if (departed || workspace.workspace_context.binding !== binding) return;
      // Optional ranking preparation must not block the established Neutral
      // workflow. Explicit requests still enforce authorization and revision
      // admission on the server. Auth, scope conflicts and Custom stay closed.
      if (!response.ok && valuationMode === 'neutral' && ![401, 403, 409].includes(response.status)) return;
      const p = workspace.personalization;
      if (!response.ok || state.revision !== p.revision || (state.generation && p.market_generation && state.generation !== p.market_generation) ||
          (state.context && (state.context.league_id !== workspace.workspace_context.league_id || Number(state.context.roster_id) !== active))) {
        personalRevisionStale = true; activeRequest?.abort(); activeRequest = null; balanceRequest = null; revision++; runSequence++; busy = false;
        session.previewProposal = null; lastOffers = null; p.values = {};
        if (session.currentAssessment) staleAssessment('Personal ranking revision or source changed');
        persist(); paint(); personalChangedNotice();
      }
    } catch (_) { /* A later explicit request still performs server-side admission and final revision checks. */ }
    finally { checkingPersonal = false; }
  }
  addEventListener('focus', checkPersonalRevision);
  addEventListener('pageshow', () => { if (workspace) checkPersonalRevision(); });
  function personalPayload() { const p = workspace?.personalization; return p ? {override_saved_protections: [...session.overrideSavedProtections], valuation_mode: valuationMode, personal_revision: p.revision, personal_market_generation: p.market_generation, personal_baseline_generation: p.baseline_generation} : {}; }
  function payload() { reconcileStrategy(); return {...personalPayload(), workflow: flow, strategy: el('trade-strategy').value || null, active_roster_id: active, partner_roster_id: partner(), assets_sent: [...selected.sent], assets_received: [...selected.received], protected_assets: [...session.protectedAssets], excluded_assets: [...session.excludedAssets], asset_id: flow === 'shop' ? session.requiredOutgoingAsset || selected.sent[0] : session.requiredIncomingAsset || selected.received[0], workspace_context: workspace.workspace_context}; }
  function persist(updateHistory = true, draftSession = session) {
    if (departed) return;
    reconcileStrategy();
    const draft = {...draftSession, valuationMode, tabOwner, strategy: el('trade-strategy').value, ownership: workspace.workspace_context.ownership_generation};
    try {
      draft.savedAt = Date.now();
      sessionStorage.setItem(storageKey(), JSON.stringify(draft));
      const keys = Object.keys(sessionStorage).filter(key => key.startsWith('dtos-trade-workspace:'));
      const savedAt = key => { try { return JSON.parse(sessionStorage.getItem(key) || '{}')?.savedAt || 0; } catch (_) { return 0; } };
      keys.sort((a,b) => savedAt(b) - savedAt(a));
      for (const key of keys.slice(12)) sessionStorage.removeItem(key);
    } catch (_) { /* Storage-disabled browsing still works in this page. */ }
    if (!updateHistory) return;
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
    const retained = JSON.parse(sessionStorage.getItem(storageKey()) || 'null');
    if (retained?.tabOwner && retained.tabOwner !== tabOwner) return {...retained, endedAtHome:true};
    if (retained?.endedAtHome) return retained;
    if (entry?.draft && entry.draft.resetGeneration !== retained?.resetGeneration && retained?.resetGeneration) {
      departed = true; location.replace('/trades/create?front_office=' + active); return retained;
    }
    if (['reload', 'back_forward'].includes(navigation) && entry?.binding === workspace.workspace_context.binding &&
        entry.workflow === flow && entry.preload === root.dataset.preloadAsset) return entry.draft;
    return JSON.parse(sessionStorage.getItem(storageKey()) || 'null');
  }
  function syncLocks() { if (el('shop-protected')) for (const option of el('shop-protected').options) option.selected = session.protectedAssets.includes(option.value); }
  function addLock(kind, id) { if (!session[kind].includes(id)) session[kind].push(id); syncLocks(); persist(); }
  function changed() { el('trade-evaluation-retained')?.remove(); session.currentAssessment = null; cancelBalance(); const focusId = document.activeElement?.dataset.assetId; revision++; session.previewProposal = null; lastOffers = null; lastOffersIsBalance = false; el('trade-result').hidden = true; el('trade-result').dataset.assessmentState = 'not_evaluated'; persist(); paint(); if (focusId) root.querySelector('button[data-asset-id="' + CSS.escape(focusId) + '"]')?.focus(); }
  function toggle(which, id) { if (busy) return; const required = which === 'sent' ? session.requiredOutgoingAsset : session.requiredIncomingAsset; if (id === required && selected[which].includes(id)) return message('The required target stays fixed. Choose Build My Own to change the trade objective.', true); if (selected[which].includes(id)) selected[which] = selected[which].filter(x => x !== id); else if (!selected.sent.includes(id) && !selected.received.includes(id)) selected[which].push(id); changed(); if ((flow === 'shop' && which === 'sent' && selected.sent.length === 1) || (flow === 'trade_for' && which === 'received' && selected.received.length === 1)) run('generate'); }
  function lockDetail(id) {
    const meanings = [];
    const kind = asset(id)?.kind || id.split(':')[0];
    if (session.protectedAssets.includes(id)) meanings.push(kind === 'pick' ? 'This exact pick cannot be added to your outgoing offer; other picks in the same round may still be used.' : kind === 'player' ? 'This player cannot be added to your outgoing offer.' : 'This exact asset cannot be added to your outgoing offer.');
    if (session.excludedAssets.includes(id)) meanings.push('Exclude this exact asset from alternatives.');
    if (id === session.requiredIncomingAsset) meanings.push('Keep this incoming Trade For target.');
    if (id === session.requiredOutgoingAsset) meanings.push('Keep this outgoing Shop anchor.');
    if (!meanings.length) return null;
    const detail = node('details', null, 'ds-badge-detail'); detail.dataset.badge = 'protection';
    detail.dataset.assetId = id;
    const title = session.protectedAssets.includes(id) ? 'Exact protected asset' : session.excludedAssets.includes(id) ? 'Excluded exact asset' : id === session.requiredOutgoingAsset ? 'Required outgoing Shop asset' : 'Required incoming Trade For target';
    detail.append(node('summary', '🔒 ' + title), node('p', label(asset(id) || {label:id}) + ' · ' + id + ': ' + meanings.join(' ')));
    return detail;
  }
  function identity(a, insideAction = false) {
    const box = node(insideAction ? 'span' : 'div');
    if (a.kind === 'player' && a.headshot_url) {
      const image = node('img'); image.src = a.headshot_url; image.alt = ''; image.loading = 'lazy';
      // Keep the reserved portrait geometry if the optional source fails.
      // Removing it changes the grid after focus/scroll and can hide controls.
      image.onerror = () => { image.onerror = null; image.style.visibility = 'hidden'; };
      box.append(image);
    }
    const position = node('span', a.position, 'ds-position'); position.dataset.position = a.position;
    box.append(node('b', label(a)), ...(a.kind === 'player' && ['QB','RB','WR','TE'].includes(a.position) ? [position] : []), node('small', a.kind === 'pick' ? [a.season, 'Round ' + a.round, 'Original: ' + label(a)].join(' · ') : [['QB','RB','WR','TE'].includes(a.position) ? null : a.position, a.nfl_team, a.positional_rank ? 'Market rank ' + a.positional_rank : null].filter(Boolean).join(' · ')));
    const protection = lockDetail(a.asset_id);
    if (protection) {
      // Asset buttons keep the interactive disclosure beside, not inside, the action.
      if (insideAction) { const lock = node('span', '🔒', 'ds-lock'); lock.setAttribute('aria-hidden', 'true'); box.append(lock); }
      else box.append(protection);
    }
    return box;
  }
  // Display-only copies: workspace ownership and selected package order stay intact.
  function pickerGroup(a) { return a.kind === 'pick' ? 'Draft picks' : (a.position || 'Other positions'); }
  function pickerAssets(assets) {
    const primary = ['QB', 'RB', 'WR', 'TE'];
    const text = (a,b) => a < b ? -1 : a > b ? 1 : 0;
    const priced = a => typeof a.trade_value === 'number' && Number.isFinite(a.trade_value);
    return [...assets].sort((a,b) => {
      if ((a.kind === 'pick') !== (b.kind === 'pick')) return a.kind === 'pick' ? 1 : -1;
      if (a.kind === 'pick') return (Number(a.season) - Number(b.season)) || (Number(a.round) - Number(b.round)) || text(String(a.original_roster_id), String(b.original_roster_id)) || text(a.asset_id,b.asset_id);
      const ap = primary.indexOf(a.position), bp = primary.indexOf(b.position);
      const group = (ap < 0 ? primary.length : ap) - (bp < 0 ? primary.length : bp);
      return group || text(pickerGroup(a),pickerGroup(b)) || Number(priced(b)) - Number(priced(a)) || (priced(a) && priced(b) ? b.trade_value - a.trade_value : 0) || text(a.asset_id,b.asset_id);
    });
  }
  function pickerOptions(select, assets) {
    let group = null, previous = null;
    for (const a of pickerAssets(assets)) {
      const name = pickerGroup(a);
      if (name !== previous) { group = node('optgroup'); group.label = name; select.append(group); previous = name; }
      const option = node('option', label(a) + (a.kind === 'pick' ? ' · ' + a.season + ' Round ' + a.round + ' · Originally ' + (team(a.original_roster_id)?.team_name || a.original_roster_id) : '') + ' · Market ' + displayMarket(a.trade_value));
      option.value = a.asset_id; group.append(option);
    }
  }
  function assetRow(a, which, review = false) {
    const row = node('div', null, 'tw-asset'), button = node('button'); button.type = 'button'; button.append(identity(a, true));
    button.append(node('strong', displayMarket(a.trade_value)));
    button.dataset.assetId = a.asset_id; button.setAttribute('aria-label', (selected[which].includes(a.asset_id) ? 'Remove ' : 'Add ') + label(a) + (which === 'sent' ? ' — you send' : ' — you receive'));
    button.disabled = busy; button.setAttribute('aria-pressed', String(selected[which].includes(a.asset_id))); button.onclick = () => toggle(which, a.asset_id); row.append(button);
    let dossier = null;
    if (a.kind === 'player') { const link = node('a', 'Dossier'); link.href = '/players/' + encodeURIComponent(a.asset_id.replace(/^player:/, '')); link.setAttribute('aria-label', 'Open ' + label(a) + ' player dossier'); dossier = link; }
    const protection = lockDetail(a.asset_id); if (protection) row.append(protection);
    const hasEvidence = a.market_fact || a.kind === 'pick';
    if (hasEvidence) {
      const evidence = review ? marketEvidence(a) : node('details');
      if (!review) evidence.append(node('summary', 'Price'));
      evidence.querySelector('summary').textContent = review ? 'Selected asset Market evidence' : 'Price';
      evidence.style.minWidth = '0'; evidence.style.overflowWrap = 'anywhere';
      if (review && dossier) evidence.append(dossier);
      if (!review) evidence.addEventListener('toggle', () => {
        if (!evidence.open || evidence.dataset.prepared) return;
        const source = marketEvidence(a);
        for (const child of Array.from(source.children).slice(1)) evidence.append(child);
        if (dossier) evidence.append(dossier);
        evidence.dataset.prepared = 'true';
      });
      row.append(evidence);
    } else if (dossier) row.append(dossier);
    if (a.trade_value == null) row.append(node('small', 'Market price unavailable', 'tw-price-warning'));
    else if (a.market_fact?.fallback) row.append(node('small', 'Retained price · check source details', 'tw-price-warning'));
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
    const results = node('div', null, 'tw-asset-results'), chips = node('div', null, 'tw-filters');
    const positions = ['ALL', 'QB', 'RB', 'WR', 'TE', ...[...new Set(owner.assets.filter(a => a.kind !== 'pick' && !['QB','RB','WR','TE'].includes(a.position)).map(a => a.position || 'Other positions'))].sort(), 'PICKS'].filter(p => p === 'ALL' || owner.assets.some(a => (a.kind === 'pick' ? 'PICKS' : (a.position || 'Other positions')) === p));
    function renderRows() { results.replaceChildren(); const rows = pickerAssets(owner.assets).filter(a => (f.pos === 'ALL' || (a.kind === 'pick' ? 'PICKS' : (a.position || 'Other positions')) === f.pos) && label(a).toLowerCase().includes(f.q.trim().toLowerCase())); let previous = null; for (const a of rows) { const group = pickerGroup(a); if (group !== previous) { const heading = node('h4', group); heading.dataset.pickerGroup = group; results.append(heading); previous = group; } results.append(assetRow(a, which)); } if (!rows.length) results.append(node('p', owner.assets.length ? 'No matching assets. Clear search or choose All.' : 'No currently owned assets available.')); }
    search.oninput = () => { f.q = search.value; renderRows(); };
    for (const pos of positions) { const b = node('button', pos); b.type = 'button'; b.dataset.position = pos; b.setAttribute('aria-pressed', String(f.pos === pos)); b.onclick = () => { f.pos = pos; board(which); container.querySelector('[data-position="' + pos + '"]').focus(); }; chips.append(b); }
    results.setAttribute('role', 'region'); results.setAttribute('aria-label', owner.team_name + ' owned assets'); results.tabIndex = 0;
    let marketLink = null;
    if (marketEditor) { marketLink = node('a', 'Review Market totals & Evaluate', 'ds-action'); marketLink.href = '#trade-balance'; }
    container.append(search, chips, results); if (marketLink) container.append(marketLink); renderRows();
  }
  function paint() {
    clearStaleBalanceFeedback();
    if (searchFeedback && (searchFeedback.offerRevision !== revision || searchFeedback.requestGeneration !== runSequence)) {
      searchFeedback = null; el('recommendation-status').textContent = ''; delete el('recommendation-status').dataset.state;
    }
    board('sent'); board('received');
    // Once Calculator has actual assets, its live comparison and Balance are
    // primary. Empty construction still begins with selectable assets.
    const calculatorPanel = root.querySelector('.tw-calculator');
    if (calculator && calculatorPanel) {
      if (selected.sent.length || selected.received.length) el('trade-board').before(calculatorPanel);
      else el('trade-board').after(calculatorPanel);
    }
    el('trade-clear-package').hidden = !session.requiredOutgoingAsset && !session.requiredIncomingAsset;
    root.querySelectorAll('[data-side]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.side === side)));
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
    paintCalculator();
    const leagueLabel = workspace.league_name || 'Selected league';
    el('trade-context').textContent = flow === 'shop' ? `Active league · ${leagueLabel} · Shop search: ${team(session.shopSearchPartner)?.team_name || 'All eligible teams'}` : `${team(active)?.team_name || 'Your franchise'} → ${team(partner())?.team_name || 'Choose partner'} · Active league · ${leagueLabel}`;
    const sourceIdentity = el('trade-source-context-identity');
    if (sourceIdentity) sourceIdentity.textContent = `League ID: ${workspace.manager_context.league_id}`;
    for (const id of ['shop-preference','shop-protected']) if (el(id)) el(id).disabled = busy;
    if (el('shop-position')) el('shop-position').disabled = busy || el('shop-preference').value !== 'position_need';
    el('trade-run').disabled = busy || !selected.sent.length || !selected.received.length;
    root.querySelectorAll('[data-reevaluate]').forEach(button => { button.disabled = el('trade-run').disabled; });
    el('trade-find').disabled = busy || entryBlocked;
    el('trade-apply-adjust').disabled = busy;
    for (const id of ['trade-alternatives', 'calculator-lock', 'trade-release-lock']) if (el(id)) el(id).disabled = busy;
    {
      el('trade-balance-offer').textContent = balanceRequest ? 'Finding balancing options…' : 'Balance offer · preview options';
      el('trade-balance-offer').setAttribute('aria-busy', String(Boolean(balanceRequest)));
    }
    el('trade-build-own').disabled = busy && !balanceRequest;
    el('trade-start-new').disabled = !workspace;
    el('trade-build-own').hidden = flow === 'create' && !session.requiredOutgoingAsset && !session.requiredIncomingAsset;
    if (el('recommendation-refresh')) el('recommendation-refresh').disabled = busy || searchExhausted;
    // Keep the calculator live status outside a busy ancestor so assistive
    // technology announces processing immediately. Balance owns aria-busy.
    root.setAttribute('aria-busy', String(busy && !marketEditor));
  }
  function paintCalculator() {
    // Exact decimal arithmetic over the prepared canonical numbers, never
    // provider normalization, a fairness probability or strategic repricing.
    const rows = ['sent', 'received'].map(which => selected[which].map(asset));
    const parts = a => marketParts(a.trade_value);
    const known = rows.flat().filter(a => a && typeof a.trade_value === 'number' && Number.isFinite(a.trade_value));
    const scale = Math.max(0, ...known.map(a => parts(a).scale));
    const units = a => { const p = parts(a); return p.integer * 10n ** BigInt(scale - p.scale); };
    const totals = rows.map(r => r.reduce((sum, a) => sum + (known.includes(a) ? units(a) : 0n), 0n));
    const shown = n => displayMarketUnits(n, scale);
    const complete = rows.every(r => r.length && r.every(a => known.includes(a)));
    const ownershipInvalid = ['sent', 'received'].some(which => selected[which].some(id => !team(which === 'sent' ? active : partner())?.assets.some(a => a.asset_id === id)));
    const box = el('trade-balance'); box.replaceChildren(node('h3', 'Market comparison'));
    rows.forEach((r, i) => box.append(node('p', `Side ${i ? 'B' : 'A'} · ${i ? 'You receive' : 'You send'}: ${r.length && r.every(a => known.includes(a)) ? shown(totals[i]) : r.some(a => known.includes(a)) ? 'Partial · known subtotal ' + shown(totals[i]) : 'Unavailable'}`)));
    const difference = totals[1] - totals[0];
    const verdict = node('h4', !complete ? rows.every(r => r.length) ? 'Cannot determine reliably · pricing evidence missing' : 'Choose assets on both sides' : difference === 0n ? 'Approximately balanced · equal Market totals' : `Side ${difference > 0n ? 'A' : 'B'} favored · ${difference > 0n ? 'you receive more' : 'your counterparty receives more'} Market value`);
    if (complete && difference !== 0n) verdict.append(node('span', ' · ' + (team(difference > 0n ? active : partner())?.team_name || 'Manager unavailable')));
    verdict.id = 'calculator-verdict'; box.append(verdict);
    if (complete) box.append(node('p', 'Value gap: ' + shown(difference < 0n ? -difference : difference) + ' Market points.'));
    if (complete) {
      const sentence = difference === 0n ? 'Market totals are equal.' : difference < 0n
        ? 'You are sending ' + shown(-difference) + ' more Market value than you receive.'
        : 'You receive ' + shown(difference) + ' more Market value than you send.';
      box.append(node('p', sentence, 'tw-market-verdict'));
      const bar = node('div', null, 'tw-market-bar'); bar.setAttribute('role', 'img');
      bar.setAttribute('aria-label', 'Relative Market totals. ' + sentence + ' Not an acceptance probability.');
      const sum = totals[0] + totals[1];
      for (let i = 0; i < 2; i++) {
        const segment = node('span', null, difference === 0n ? 'neutral' : (i === 1) === (difference > 0n) ? 'advantage' : 'disadvantage');
        segment.style.flexBasis = (sum > 0n ? Number(totals[i] * 10000n / sum) / 100 : 50) + '%'; bar.append(segment);
      }
      const caption = node('div', null, 'tw-market-caption'); caption.append(node('span', 'You send ' + shown(totals[0]) + ' · They receive'), node('span', 'You receive ' + shown(totals[1])));
      box.append(caption, bar, node('small', 'Relative asset value · not an acceptance probability.'));
    }
    if (ownershipInvalid) box.append(node('p', 'Ownership invalid or unavailable: this retained hypothetical offer is not executable. Remove moved assets or select their current owner before balancing.', 'tw-error'));
    box.append(node('small', 'Market value ≠ lineup impact ≠ future capital ≠ strategy fit. Evaluate separately.'));
    let selectedValueComplete = complete, selectedValueDifference = difference;
    if (valuationMode === 'custom') {
      const values = workspace.personalization?.values || {};
      const personalRows = ['sent', 'received'].map(which => selected[which].map(id => values[id]));
      const knownPersonal = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
      const personalScale = Math.max(0, ...personalRows.flat().filter(knownPersonal).map(value => marketParts(value).scale));
      const personalUnits = value => { const p = marketParts(value); return p.integer * 10n ** BigInt(personalScale - p.scale); };
      const personalTotals = personalRows.map(row => row.length && row.every(knownPersonal)
        ? row.reduce((sum, value) => sum + personalUnits(value), 0n) : null);
      selectedValueComplete = complete && personalTotals.every(total => total != null);
      selectedValueDifference = selectedValueComplete ? personalTotals[1] - personalTotals[0] : 0n;
      const panel = node('section', null, 'tw-personal-comparison');
      panel.append(node('h3', 'Your Custom DTOS valuation'), node('p', `You send: ${personalTotals[0] == null ? 'Unavailable' : displayMarketUnits(personalTotals[0], personalScale)} · You receive: ${personalTotals[1] == null ? 'Unavailable' : displayMarketUnits(personalTotals[1], personalScale)}`), node('small', 'Saved rank-slot values express your preferences. The neutral Market comparison below and opponent evidence are unchanged.'));
      if (personalRows.flat().some(value => !knownPersonal(value))) panel.append(node('p', 'This package includes an asset without a verified personal value. Check its saved rank and affected assets in My DTOS, or use Neutral DTOS. Your offer is unchanged.'));
      box.prepend(panel);
    }
    const locks = [...new Set([...session.protectedAssets, ...session.excludedAssets, session.requiredOutgoingAsset, session.requiredIncomingAsset].filter(Boolean))];
    if (locks.length) {
      const details = node('details', null, 'ds-badge-detail'); details.dataset.badge = 'protection-summary';
      details.append(node('summary', '🔒 Exact protections: ' + locks.length));
      for (const id of locks) details.append(lockDetail(id).querySelector('p'));
      box.append(details);
    }
    if (selected.sent.some(id => session.protectedAssets.includes(id)) || [...selected.sent, ...selected.received].some(id => session.excludedAssets.includes(id))) box.append(node('p', 'Protected-asset conflict: remove the protected asset from this offer or explicitly release its lock.', 'tw-error'));
    for (const which of ['sent', 'received']) {
      const list = el('calculator-' + which); if (!list) continue; list.replaceChildren();
      if (!selected[which].length) list.append(node('p', 'No assets selected.'));
      for (const id of selected[which]) {
        const a = asset(id), row = node('div', null, 'tw-calculator-asset');
        const owner = workspace.teams.find(t => t.assets.some(item => item.asset_id === id));
        const identity = node('span', null, 'tw-calculator-identity');
        identity.append(node('b', a ? label(a) : 'Ownership unavailable'), node('small', [a?.kind === 'pick' ? 'Pick' : a?.position || 'Position unavailable', a?.nfl_team, owner?.team_name || 'Owner unavailable', a?.trade_value != null ? displayMarket(a.trade_value) : 'Market unavailable'].filter(value => value != null && value !== '').join(' · ')));
        row.append(identity);
        const remove = node('button', 'Remove'); remove.type = 'button'; remove.disabled = busy; remove.setAttribute('aria-label', 'Remove ' + (a ? label(a) : id) + ' from calculator'); remove.onclick = () => toggle(which, id); row.append(remove); const protection = lockDetail(id); if (protection) row.append(protection); list.append(row);
        const evidence = marketEvidence(a); if (evidence) list.append(evidence);
        if (which === 'received' && a) {
          const keep = node('button', session.requiredIncomingAsset === id ? 'Release incoming target' : 'Keep incoming target'); keep.type = 'button'; keep.disabled = busy; keep.onclick = () => { if (busy) return; session.requiredIncomingAsset = session.requiredIncomingAsset === id ? null : id; changed(); }; list.append(keep);
        }
      }
    }
    el('trade-balance-offer').disabled = busy || !selectedValueComplete || ownershipInvalid || selectedValueDifference === 0n;
  }
  function review() {
    el('trade-review').hidden = false;
    el('trade-board').hidden = true;
    // Focus must not schedule a second scroll after the board collapses.
    el('trade-review').focus({preventScroll: true});
    el('trade-review').scrollIntoView({block: 'start', behavior: 'instant'});
  }
  function edit() { if (flow === 'trade_for' && selected.received.length) { side = 'sent'; paint(); } el('trade-board').hidden = false; el('trade-review').hidden = true; el('trade-assist').hidden = true; el('trade-partner').focus(); }
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
        staleAssessment('Source evidence changed');
        const error = new Error('Market or projection evidence refreshed during this search. Your proposal and exact protections are unchanged. Try again when the refresh settles.');
        error.code = code; throw error;
      }
      const error = new Error(d?.message || (typeof d === 'string' ? d : "DTOS couldn't complete this evaluation. Your proposal is still intact."));
      error.code = code;
      if (d?.recovery_url === '/account/my-dtos#personal-compatibility') error.personalRecovery = true;
      throw error;
    }
    return body;
  }
  // Persist only the existing structured evidence, never rendered HTML or a
  // search result cache. Limits apply to every node and the complete context.
  function boundedEvidence(value, depth = 0, budget = {remaining: 12000, nodes: 512}) {
    if (depth > 9 || budget.nodes-- <= 0) return null;
    if (typeof value === 'string') { const text = value.slice(0, Math.min(1600, budget.remaining)); budget.remaining -= text.length; return text; }
    if (value == null || typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value))) return value;
    if (Array.isArray(value)) return value.slice(0, 32).map(v => boundedEvidence(v, depth + 1, budget)).filter(v => v !== null);
    if (typeof value !== 'object') return null;
    return Object.fromEntries(Object.entries(value).filter(([key]) => !['explanation_html', '__proto__', 'constructor', 'prototype'].includes(key))
      .slice(0, 64).map(([key, v]) => [key.slice(0, 80), boundedEvidence(v, depth + 1, budget)]));
  }
  const packageIdentity = p => JSON.stringify([Number(p.partner_roster_id ?? p.partner), [...(p.assets_sent || p.sent || [])].sort(), [...(p.assets_received || p.received || [])].sort()]);
  function compactRetainedEvaluation(value) {
    // Keep the existing 12k-character/512-node saved-context limits. Reserve
    // evidence is shared by three live DTO views; retain it once, with repeated
    // qualifications interned, so it cannot crowd out earlier decision facts.
    if (!value || typeof value !== 'object') return value;
    const withoutReserveCopies = row => {
      if (!row || typeof row !== 'object') return row;
      const {reserve_quality_by_week, reserve_quality, ...rest} = row;
      return rest;
    };
    const compactPackage = row => {
      if (!row || typeof row !== 'object' || !row.reserve_quality_by_week || row.reserve_quality_encoding === 'tuple-v1') return row;
      const qualifications = [];
      const weeks = Object.fromEntries(Object.entries(row.reserve_quality_by_week).map(([week, evidence]) => {
        const refs = (evidence?.limitations || []).map(text => {
          if (!qualifications.includes(text)) qualifications.push(text);
          return qualifications.indexOf(text);
        });
        return [week, JSON.stringify([evidence?.pre_points, evidence?.post_points, evidence?.delta,
          evidence?.pre_slots, evidence?.post_slots, evidence?.conclusion_state,
          evidence?.projection_freshness, evidence?.material_weekly_threshold,
          evidence?.material_gain, evidence?.material_loss, evidence?.availability, refs])];
      }));
      return {...row, reserve_quality_by_week: weeks, reserve_quality_encoding: 'tuple-v1', reserve_qualifications: qualifications};
    };
    const dims = value.dimensions || {}, strategies = dims.strategic_fit, packages = dims.package_quality;
    const reserveEvidence = value.reserve_evidence || (packages ? Object.fromEntries(Object.entries(packages)
      .filter(([, row]) => row?.reserve_quality_by_week).map(([key, row]) => {
        const compact = compactPackage(row);
        return [key, {reserve_quality_by_week: compact.reserve_quality_by_week,
          reserve_quality_encoding: compact.reserve_quality_encoding, reserve_qualifications: compact.reserve_qualifications}];
      })) : null);
    const trace = withoutReserveCopies(value.recommendation_trace);
    // Trace duplicates already-rendered strategy facts. Preserve its remaining
    // structured metadata in bounded strings instead of spending another node
    // per scalar before either team's earlier lineup evidence can be retained.
    const compactTrace = !trace || trace.detail_encoding === 'entries-v1' ? trace : {
      rule_reasons: trace.rule_reasons, scope: trace.scope, detail_encoding: 'entries-v1',
      details: Object.entries(trace).filter(([key]) => !['rule_reasons', 'scope'].includes(key))
        .map(entry => JSON.stringify(entry))};
    // Intern each admitted comparison once within the unchanged 12k/512-node
    // context bound. Never revive raw strategy numbers after HTML is discarded.
    const rows = value => value ? Object.fromEntries(Object.entries(value).map(([key,row]) =>
      [key, typeof row === 'string' ? row : JSON.stringify(row)])) : value;
    const d = value.decision_context;
    const compactDecision = d ? {...d, lineup_comparisons: rows(d.lineup_comparisons),
      partner_lineup_comparisons: rows(d.partner_lineup_comparisons),
      lineup_phase_admission: d.lineup_phase_admission ? Object.fromEntries(Object.entries(d.lineup_phase_admission)
        .map(([side,weeks]) => [side,rows(weeks)])) : d.lineup_phase_admission} : d;
    return {reserve_evidence: reserveEvidence, ...value, decision_context: compactDecision, recommendation_trace: compactTrace,
      dimensions: {...dims,
        strategic_fit: strategies ? {...strategies, active: withoutReserveCopies(strategies.active), partner: withoutReserveCopies(strategies.partner)} : strategies,
        package_quality: packages ? Object.fromEntries(Object.entries(packages).map(([key, row]) => [key, withoutReserveCopies(row)])) : packages}};
  }
  function retainedReserveRow(row, quality) {
    if (typeof row !== 'string' || quality?.reserve_quality_encoding !== 'tuple-v1') return row;
    try {
      const values = JSON.parse(row);
      if (!Array.isArray(values) || values.length !== 12) return null;
      return {pre_points: values[0], post_points: values[1], delta: values[2], pre_slots: values[3], post_slots: values[4],
        conclusion_state: values[5], projection_freshness: values[6], material_weekly_threshold: values[7],
        material_gain: values[8], material_loss: values[9], availability: values[10],
        limitations: (values[11] || []).map(index => quality.reserve_qualifications?.[index]).filter(text => typeof text === 'string')};
    } catch (_) { return null; }
  }
  function restoreContext(value, includePrevious = true) {
    return {schema: 1, identity: boundedEvidence(value.identity || {}), exploration: value.exploration === true,
      search_result_type: boundedEvidence(value.search_result_type), stale_reason: boundedEvidence(value.stale_reason), restored: true,
      attempt_state: value.attempt_state || value.evaluation?.assessment_state?.state || 'fresh_incomplete',
      previous_assessment: includePrevious && value.previous_assessment ? restoreContext(value.previous_assessment, false) : null,
      evaluation: boundedEvidence(compactRetainedEvaluation(value.evaluation || {})), opportunity: boundedEvidence(value.opportunity)};
  }
  const assessedOfferContexts = new WeakMap();
  function assessmentContext(row) {
    if (assessedOfferContexts.has(row)) return assessedOfferContexts.get(row);
    if (row.proposal?.preview_context) return row.proposal.preview_context;
    const e = row.evaluation || row.proposal?.preview_assessment || {};
    const keys = ['personalization', 'personal_value_evidence', 'neutral_assessment', 'recommendation', 'dominant_reason', 'major_drawback', 'why_you_would_do_it', 'why_they_would_do_it', 'counterparty_summary', 'provenance', 'major_risks', 'major_limitations', 'recommendation_trace', 'legality', 'decision_context', 'market_evidence', 'dimensions', 'assessment_state', 'reserve_evidence', 'personalization', 'personal_value_evidence', 'neutral_assessment', 'neutral_values', 'personal_preference_warnings', 'personal_preference_conflicts'];
    const context = {schema: 1, evaluation: boundedEvidence(compactRetainedEvaluation(Object.fromEntries(keys.filter(key => key in e).map(key => [key, e[key]])))),
      exploration: row.exploration === true, search_result_type: row.search_result_type || null,
      opportunity: boundedEvidence(row.opportunity || null),
      identity: {personalization: JSON.stringify(personalPayload()), package: packageIdentity(row.proposal || selected), strategy: row.home_assessment_strategy ?? el('trade-strategy').value,
        source: row.home_source_identity || row.assessment_source_identity || null,
        workflow: row.workflow || session.originWorkflow, binding: workspace.workspace_context.binding,
        ownership: workspace.workspace_context.ownership_generation, market: workspace.calculator_generation,
        captured_at: new Date().toISOString(), counterparty: team(row.proposal?.partner_roster_id || partner())?.team_name || null}};
    if (JSON.stringify(context).length > 64000) {
      // Retain primary meaning and provenance even for unusually deep evidence.
      context.evaluation.dimensions = boundedEvidence({confidence: {assessment: e.dimensions?.confidence?.assessment, explanation: e.dimensions?.confidence?.explanation}, counterparty_plausibility: {assessment: e.dimensions?.counterparty_plausibility?.assessment, explanation: e.dimensions?.counterparty_plausibility?.explanation}});
      context.opportunity = null;
      context.identity.package = context.identity.package.slice(0, 16000);
      context.evaluation.major_limitations = [...(context.evaluation.major_limitations || []), 'Additional evidence omitted from temporary preview; reevaluate for full details.'].slice(-32);
    }
    return context;
  }
  function contextQualification(context, proposal = selected) {
    if (!context) return '';
    const identity = context.identity || {}, reasons = [];
    if (identity.package !== packageIdentity(proposal)) reasons.push('package changed');
    if (identity.strategy !== el('trade-strategy').value) reasons.push('strategy changed');
    if (identity.binding !== workspace.workspace_context.binding || identity.ownership !== workspace.workspace_context.ownership_generation) reasons.push('ownership context changed');
    if (identity.market !== workspace.calculator_generation) reasons.push('Market evidence changed');
    if (identity.personalization && identity.personalization !== JSON.stringify(personalPayload())) reasons.push('personal valuation mode or ranking revision changed');
    if (!identity.personalization && valuationMode === 'custom') reasons.push('personal valuation identity unavailable');
    const inputs = context.evaluation?.provenance?.inputs || {};
    for (const key of sourceKeys) if (Object.hasOwn(latestEvidence, key) && Object.hasOwn(inputs, key) && inputs[key] !== latestEvidence[key]) reasons.push(key.replace('_generation', '') + ' evidence changed');
    if (context.restored && workspace.projection_evidence && !Object.hasOwn(inputs, 'projection_generation')) reasons.push('projection identity unavailable in retained context');
    if (context.stale_reason) reasons.push(context.stale_reason);
    return context.restored || reasons.length ? 'Retained assessment context · not revalidated. ' + (reasons.length ? reasons.join('; ') + '. ' : '') + 'Reevaluate to establish a current assessment; prior benefits and drawbacks are retained.' : '';
  }
  function contextNotice(out, context, proposal) {
    if (context?.exploration) out.append(node('p', 'Exploratory only · ' + (context.search_result_type || 'supported alternative') + ' · not a qualified bilateral recommendation', 'tw-drawback'));
    if (context?.identity?.ownership && context.identity.ownership !== workspace.workspace_context.ownership_generation) out.append(node('p', 'Ownership has changed. Your proposal is retained for review; evaluation will identify any assets that moved.', 'tw-drawback'));
    if (context?.identity) { const summary = node('p', 'Assessment strategy: ' + (context.identity.strategy || 'Use supported competitive window') + ' · Current selected strategy: ' + (el('trade-strategy').value || 'Use supported competitive window')); summary.dataset.assessmentStrategy = context.identity.strategy || ''; out.append(summary); }
    const qualification = contextQualification(context, proposal);
    if (qualification) { out.append(node('p', qualification, 'tw-drawback')); reevaluateAction(out); }
  }
  function reevaluateAction(out) {
    if (out.querySelector('[data-reevaluate]')) return;
    const button = node('button', 'Reevaluate Trade'); button.type = 'button'; button.dataset.reevaluate = 'true';
    button.disabled = busy || !selected.sent.length || !selected.received.length;
    button.onclick = () => run('evaluate'); out.append(button);
  }
  function assessedRows(body) {
    // Explicit bounded response collections; no arbitrary payload traversal.
    return [...(body.results || []), ...(body.exploratory_results || []), ...(body.near_misses || []),
      ...(body.comparisons || []), ...(body.markets || []).flatMap(m => m.returns || []),
      ...(body.evaluation ? [{evaluation: body.evaluation}] : [])];
  }
  function observeEvidence(body) {
    const rows = assessedRows(body).filter(row => !row.evaluation?.provenance?.inputs?.league_id || row.evaluation.provenance.inputs.league_id === workspace.manager_context.league_id);
    for (const row of rows) {
      const inputs = row.evaluation?.provenance?.inputs;
      if (!inputs) continue;
      for (const key of sourceKeys) if (Object.hasOwn(inputs, key)) latestEvidence[key] = inputs[key];
    }
    const changedSource = context => {
      const inputs = context?.evaluation?.provenance?.inputs;
      return inputs && sourceKeys.some(key => Object.hasOwn(inputs, key) && Object.hasOwn(latestEvidence, key) && inputs[key] !== latestEvidence[key]);
    };
    if (changedSource(session.currentAssessment)) staleAssessment('Source evidence changed since the completed assessment');
    if (changedSource(session.previewProposal?.preview_context)) { session.previewProposal.preview_context.restored = true; session.previewProposal.preview_context.stale_reason = 'Source evidence changed since this preview'; persist(); }
  }
  function retainAssessment() {
    if (!session.currentAssessment || el('trade-evaluation-retained')) return;
    if (!el('trade-result').dataset.assessment) showEvaluation(session.currentAssessment.evaluation || {}, session.currentAssessment.opportunity, session.currentAssessment);
    const retained = node('section'); retained.id = 'trade-evaluation-retained'; retained.setAttribute('aria-label', 'Current offer assessment');
    retained.append(...el('trade-result').childNodes); el('trade-balancing').before(retained);
  }
  function staleAssessment(reason) {
    if (!session.currentAssessment) return;
    const retained = Boolean(el('trade-evaluation-retained'));
    session.currentAssessment.restored = true; session.currentAssessment.stale_reason = reason;
    showEvaluation(session.currentAssessment.evaluation, session.currentAssessment.opportunity, session.currentAssessment);
    if (retained) retainAssessment();
    persist();
  }
  function finalVerdict(e) {
    if (e.decision_context?.final_decision) return e.decision_context.final_decision.headline;
    // Older retained responses lack the presentation contract. Never elevate
    // user-side upside over their recorded bilateral admission.
    if (e.generated_trade_eligible !== true && ['SMASH ACCEPT', 'WORTH PURSUING'].includes(e.recommendation)) {
      if (e.legal === false || ['NOT EXECUTABLE', 'REQUIRES ROSTER RESOLUTION'].includes(e.legality?.execution_status)) return 'NOT EXECUTABLE';
      if (e.market_evidence?.availability !== 'full') return 'Recommendation unavailable';
      if (!['STRONG', 'PLAUSIBLE'].includes(e.dimensions?.counterparty_plausibility?.assessment)) return 'COUNTERPARTY LIMITED';
      return 'Not a qualified recommendation';
    }
    return e.recommendation || 'Recommendation unavailable';
  }
  function parsedExplanation(e) {
    const parsed = new DOMParser().parseFromString(e.explanation_html, 'text/html');
    const primary = parsed.querySelector('.dtos-explanation > p');
    // Older cached HTML must follow the same recorded bilateral admission in
    // expanded cards and previews as in the main result. No re-evaluation.
    if (primary && primary.firstChild?.textContent.trim() === e.recommendation && finalVerdict(e) !== e.recommendation) {
      primary.replaceChildren(node('span', finalVerdict(e)), node('span', 'Not a qualified bilateral recommendation; your-side assessment is separate.', 'tw-verdict-qualification'));
    }
    return parsed;
  }
  function decisionPresentation(e) {
    const decision = {...(e.decision_context || {})};
    const row = value => {
      if (typeof value !== 'string') return value;
      try { const parsed = JSON.parse(value); return parsed && typeof parsed === 'object' ? parsed : null; }
      catch (_) { return null; }
    };
    const rows = value => Object.fromEntries(Object.entries(value || {}).map(([key,value]) => [key,row(value)]));
    decision.lineup_comparisons = rows(decision.lineup_comparisons);
    decision.partner_lineup_comparisons = rows(decision.partner_lineup_comparisons);
    decision.lineup_phase_admission = Object.fromEntries(Object.entries(decision.lineup_phase_admission || {})
      .map(([side,weeks]) => [side,rows(weeks)]));
    // Presentation admission for older bounded saved fields, not re-evaluation.
    // Prefer the server qualification; preserve the canonical label/eligibility.
    if (['partial', 'unavailable'].includes(e.market_evidence?.availability)) {
      if (e.generated_trade_eligible !== true && ['SMASH ACCEPT', 'WORTH PURSUING'].includes(e.recommendation))
        decision.qualification ||= 'Conditional exploration · not an endorsement. Required Market pricing is missing or incompatible.';
      const unknownCost = 'Market cost cannot be fully assessed because required pricing is missing or incompatible.';
      const cost = decision.main_cost || e.major_drawback || '';
      const knownCost = cost.replace(/^No material downside identified in supported evidence; projections remain conditional\.\s*/, '');
      if (!cost.includes(unknownCost)) decision.main_cost = unknownCost + (knownCost ? ' ' + knownCost : '');
    }
    return decision;
  }
  function catalystDelta(c, decision) {
    // Copied opportunity labels cannot qualify their own numbers. Reuse the
    // already-admitted period and source; never fill a missing comparison.
    if (!decision.lineup_source_generation || c.generation !== decision.lineup_source_generation || !Array.isArray(c.weeks)) return null;
    const numeric = value => typeof value === 'number' && Number.isFinite(value);
    if (c.type === 'UPCOMING_BYE_LINEUP_FIT' && c.weeks.length === 1) {
      const value = decision.lineup_weekly_comparisons?.[c.side]?.[String(c.weeks[0])];
      return numeric(value) && c.delta === value ? value : null;
    }
    const periods = c.side === 'active' ? decision.lineup_comparisons : c.side === 'partner' ? decision.partner_lineup_comparisons : {};
    const period = periods?.[c.horizon];
    return numeric(period?.delta) && c.delta === period.delta && JSON.stringify(c.weeks) === JSON.stringify(period.weeks) ? period.delta : null;
  }
  function appendLineupComparisons(out, e, horizons, title, retained) {
      for (const [key, horizon] of Object.entries(horizons)) {
        if (!horizon || typeof horizon !== 'object') continue;
        const label = {current_week: 'Current week', next_n: 'Next-N', rest_of_regular_season: 'Rest of regular season', playoff_window: 'Playoff window'}[key] || key;
        out.append(node('p', `${title} · ${label}: ${displayPoints(horizon.delta)}`),
          node('small', `Season ${e.provenance?.inputs?.projection_evidence?.season ?? 'not verified'} · weeks ${(horizon.weeks || []).join(', ') || 'not verified'}. ${['supported','provisional'].includes(horizon.state) ? 'Source-qualified optimal before versus optimal after; availability remains conditional where stated.' : 'A complete source-compatible comparison cannot be verified.'}`));
        if (retained && horizon.pre_total != null && horizon.post_total != null)
          out.append(node('p', `${title} at the previous assessment · ${label}: ${displayPoints(horizon.pre_total)} → ${displayPoints(horizon.post_total)} Sleeper-projected legal-lineup points. Earlier evidence, not current or revalidated.`));
        if (horizon.delta == null && horizon.subtotal != null)
          out.append(node('small', `Comparable-week change subtotal: ${displayPoints(horizon.subtotal)} across ${horizon.comparable_weeks?.length || 0} weeks. Not a complete horizon projection.`));
      }
  }
  function showEvaluation(e, opportunity = null, context = null, previousContainer = null) {
    const decision = decisionPresentation(e);
    const out = previousContainer || el('trade-result');
    if (!previousContainer) {
      el('trade-evaluation-retained')?.remove(); root.append(out); root.append(el('trade-balancing')); out.hidden = false; out.className = ''; out.replaceChildren();
      const marketDetail = root.querySelector('.tw-market-detail'); if (marketDetail) root.append(marketDetail);
      contextNotice(out, context, selected);
    } else {
      out.setAttribute('aria-label', 'Previous assessment · NOT REVALIDATED · not current');
      out.append(node('p', 'These details reflect the earlier evaluation, not current conclusions. Its Market, lineup, counterparty and execution evidence have not been revalidated.', 'tw-drawback'));
      out.append(node('p', 'Earlier analysis strategy: ' + (context?.identity?.strategy || 'Use supported competitive window') + ' · Counterparty at assessment: ' + (context?.identity?.counterparty || 'Unavailable')));
      try {
        const [, sent, received] = JSON.parse(context?.identity?.package || 'null');
        const names = ids => ids.map(id => asset(id) ? label(asset(id)) : id + ' (saved exact identity; display name unavailable)').join(' + ') || 'None';
        if (Array.isArray(sent) && Array.isArray(received)) out.append(node('p', 'Earlier you send: ' + names(sent)), node('p', 'Earlier you receive: ' + names(received)));
      } catch (_) { out.append(node('p', 'Earlier exact package identities unavailable in retained context.')); }
    }
    out.dataset.assessment = 'true';
    const retained = Boolean(previousContainer || contextQualification(context));
    out.dataset.assessmentFreshness = retained ? 'retained' : 'current';
    const attemptState = context?.attempt_state || e.assessment_state?.state || 'fresh_incomplete';
    out.dataset.assessmentState = retained ? 'retained' : attemptState;
    const incomplete = !retained && attemptState === 'fresh_incomplete';
    if (incomplete) {
      out.append(node('p', 'Current evaluation completed · incomplete evidence. ' + (e.assessment_state?.limitation || e.decision_context?.blocker || e.decision_context?.limitation || 'A complete supported recommendation is unavailable; review the evidence and reevaluate.'), 'tw-assessment-status'));
      reevaluateAction(out);
    }
    if (e.personalization?.mode === 'custom') {
      out.append(node('h3', 'Custom DTOS · your personal assessment'), node('p', 'Neutral DTOS: ' + (e.neutral_assessment?.recommendation || 'Unavailable') + '. Market prices and your counterparty’s supported evidence remain neutral.', 'tw-verdict-qualification'));
      const value = e.personal_value_evidence;
      if (value) out.append(node('p', 'Your personal values from Custom Rankings · You send ' + (value.sent?.total == null ? 'Unavailable' : displayMarket(value.sent.total)) + ' / You receive ' + (value.received?.total == null ? 'Unavailable' : displayMarket(value.received.total))));
    }
    for (const warning of e.personal_preference_warnings || []) out.append(node('p', warning + '. Your manually entered offer was not altered.', 'tw-drawback'));
    if (!retained) for (const conflict of e.personal_preference_conflicts || []) {
      if (conflict.kind !== 'protect') continue;
      const override = node('button', session.overrideSavedProtections.includes(conflict.asset_id) ? 'Restore saved protection for ' + label(asset(conflict.asset_id) || {label: conflict.asset_id}) : 'Allow ' + label(asset(conflict.asset_id) || {label: conflict.asset_id}) + ' in suggestions for this trade only');
      override.type = 'button'; override.onclick = () => {
        if (busy) return;
        if (session.overrideSavedProtections.includes(conflict.asset_id)) session.overrideSavedProtections = session.overrideSavedProtections.filter(id => id !== conflict.asset_id);
        else session.overrideSavedProtections.push(conflict.asset_id);
        revision++; session.previewProposal = null; persist(); message('Temporary protection override updated. Saved My DTOS preferences are unchanged. Run an explicit search or adjustment to use it.');
      };
      out.append(override);
    }
    if (retained) out.append(node('h4', 'Previous assessment explanation · NOT REVALIDATED'));
    if (!previousContainer && context?.previous_assessment) {
      const prior = context.previous_assessment, detail = node('details');
      detail.append(node('summary', 'Previous assessment · NOT REVALIDATED'));
      // Render the already-bounded saved fields; no re-evaluation, new copy or
      // persistence. Embedded rendering cannot move the current result/actions.
      showEvaluation(prior.evaluation || {}, prior.opportunity, prior, detail);
      out.append(detail);
    }
    if (e.explanation_html) {
      // Same-origin server renderer escapes all evidence text. No client-side
      // recommendation/scoring or reason-code interpretation is performed.
      const document = parsedExplanation(e);
      if (incomplete && e.recommendation && e.assessment_state?.recommendation_supported !== true) {
        const conclusion = document.querySelector('.dtos-explanation > p');
        if (conclusion) conclusion.textContent = 'Recommendation unavailable · current evaluation is incomplete.';
      }
      if (retained) {
        const explanation = document.querySelector('.dtos-explanation');
        if (explanation) {
          explanation.dataset.assessmentFreshness = 'retained';
          explanation.setAttribute('aria-label', 'Previous assessment explanation · not current');
          const conclusion = explanation.querySelector(':scope > p');
          if (conclusion) { conclusion.dataset.retainedConclusion = 'true'; conclusion.setAttribute('aria-label', 'Retained prior assessment: ' + conclusion.textContent + ' · not revalidated'); }
        }
      }
      out.append(...document.body.childNodes);
      if (!previousContainer && e.decision_context?.strategy?.selection_required) strategyAction(out);
      const balanceLink = node('a', 'Options to balance this trade', 'ds-action'); balanceLink.href = '#trade-balancing';
      if (!previousContainer) out.querySelector('.dtos-explanation > p')?.after(balanceLink);
      if (e.legality?.execution_status && !retained && (!incomplete || e.legal === false || e.legality.execution_status === 'REQUIRES ROSTER RESOLUTION')) out.append(node('p', e.legality.execution_status));
    } else {
    out.append(node('h3', retained ? 'Retained assessment: ' + (e.recommendation || 'Unavailable') + ' · NOT REVALIDATED' : incomplete && e.assessment_state?.recommendation_supported !== true ? 'Recommendation unavailable' : finalVerdict(e)), node('p', retained ? 'Previous assessment reasoning (not current): ' + (e.dominant_reason || 'Unavailable') : e.dominant_reason));
    if (previousContainer && e.market_evidence) {
      const m = e.market_evidence, side = name => m[name]?.total != null ? displayMarket(m[name].total) : m[name]?.known_subtotal != null ? 'Incomplete · known subtotal ' + displayMarket(m[name].known_subtotal) : 'Unavailable';
      out.append(node('h4', 'Market evidence at the previous assessment'),
        node('p', `You send ${side('sent')} / You receive ${side('received')}. Difference: ${m.availability === 'full' && m.difference != null ? displayMarket(Math.abs(m.difference)) : 'Unavailable · incomplete comparison'}.`),
        node('small', 'Retained displayed values, not new quotes or trade-date grades.'));
    }
    if (decision.qualification) out.append(node('p', decision.qualification, 'tw-verdict-qualification'));
    if (e.decision_context) {
      const brief = node('section', null, 'tw-decision');
      if (retained) brief.append(node('p', 'Previous decision context · NOT REVALIDATED. Numbers and conclusions below describe the original assessment.'));
      for (const text of [decision.blocker, decision.lineup?.explanation, decision.summary, decision.coverage_explanation, decision.limitation]) if (text) brief.append(node('p', text));
      out.append(brief);
      if (!previousContainer && e.decision_context.strategy?.selection_required) strategyAction(out);
    }
    if (decision.main_cost || e.major_drawback || e.major_risks?.length) out.append(node('p', 'Cost and uncertainty: ' + (decision.main_cost || e.major_drawback || e.major_risks.join('; ').replaceAll('_', ' ')), 'tw-drawback'));
    else if (context?.restored) out.append(node('p', 'Major drawback unavailable in retained context. Reevaluate for supported costs.', 'tw-drawback'));
    if (previousContainer) for (const risk of e.major_risks || []) if (risk !== e.major_drawback) out.append(node('p', 'Previous risk: ' + risk.replaceAll('_', ' '), 'tw-drawback'));
    if (e.legality?.execution_status && !retained && (!incomplete || e.legal === false || e.legality.execution_status === 'REQUIRES ROSTER RESOLUTION')) out.append(node('p', e.legality.execution_status));
    if (e.recommendation_trace) {
      const trace = node('details'); trace.append(node('summary', 'Recommendation evidence'));
      for (const reason of decision.lineup_rationale_verified?.active === false ? [] : e.recommendation_trace.rule_reasons || []) trace.append(node('p', reason.replaceAll('_', ' ')));
      trace.append(node('small', e.recommendation_trace.scope)); out.append(trace);
    }
    for (const [title, value] of [['Why you may do it', decision.summary || e.why_you_would_do_it], ['Why they may do it', decision.partner_summary || e.why_they_would_do_it]]) if (value) out.append(node('h4', title), node('p', value));
    if (retained && (decision.partner_summary || e.counterparty_summary)) out.append(node('h4', 'Previous counterparty package explanation · NOT REVALIDATED'), node('p', decision.partner_summary || e.counterparty_summary));
    for (const [key, dim] of Object.entries(e.dimensions || {})) if (dim && dim.assessment) {
      const detail = node('details'); detail.append(node('summary', (dim.label || key.replaceAll('_', ' ')) + ': ' + dim.assessment));
      if (dim.explanation) detail.append(node('p', key === 'counterparty_plausibility' && decision.lineup_rationale_verified?.partner === false ? decision.partner_summary : dim.explanation));
      for (const reason of dim.reasons || []) detail.append(node('p', reason));
      if (key === 'confidence' && dim.dimensions) {
        const coverage = dim.dimensions;
        if (coverage.market) detail.append(node('p', `Market coverage: ${coverage.market.priced_assets}/${coverage.market.asset_count} assets (${coverage.market.availability}).`));
        if (coverage.fois) detail.append(node('p', `FOIS context: ${coverage.fois.availability}. This is not an acceptance probability.`));
        for (const [side, horizons] of Object.entries(coverage.projection_and_lineup || {}))
          for (const [name, row] of Object.entries(horizons)) detail.append(node('p', `${side} · ${name.replaceAll('_', ' ')}: ${row.availability}`));
      }
      out.append(detail);
    }
    for (const [which, title] of [['active', 'Your team'], ['partner', 'Their team']]) {
      const impact = e.lineup_impact?.[which], quality = e.dimensions?.package_quality?.[which];
      const reserveEvidence = e.reserve_evidence?.[which] || quality;
      const verified = decision.lineup_rationale_verified?.[which];
      if (quality) out.append(node('p', title + ' package: ' + quality.assessment), node('small', verified === false ? 'The recorded package-production rationale cannot be verified.' : quality.explanation));
      const horizons = (which === 'active' ? decision.lineup_comparisons : decision.partner_lineup_comparisons) || {};
      if (impact) out.append(node('p', title + ' projected lineup change: ' + displayPoints(horizons.current_week?.delta)), node('small', 'Source-qualified optimal legal lineup, before versus after; missing comparison evidence is not zero.'));
      const strategy = e.dimensions?.strategic_fit?.[which];
      if (strategy) {
        const detail = node('details'); detail.append(node('summary', title + ' strategic evidence'));
        for (const reason of verified === false ? [] : strategy.reason_codes || []) detail.append(node('p', reason.replaceAll('_', ' ')));
        const reserves = reserveEvidence?.reserve_quality_by_week || strategy.reserve_quality_by_week || {};
        if (Object.keys(reserves).length) {
          detail.append(node('p', retained ? 'Previous useful replacement production · NOT REVALIDATED' : 'Useful replacement production'));
          for (const [week, savedRow] of Object.entries(reserves)) {
            const row = retainedReserveRow(savedRow, reserveEvidence);
            if (!row) { detail.append(node('p', `Week ${week}: retained reserve details are incomplete; reevaluate for current evidence.`)); continue; }
            const admitted = decision.lineup_phase_admission?.[which]?.[week] || [];
            const number = value => typeof value === 'number' && Number.isFinite(value) ? (Object.is(value, -0) ? 0 : value).toFixed(2) : 'unavailable';
            detail.append(node('p', `Week ${week}: ${number(admitted[0] === true ? row.pre_points : null)} → ${number(admitted[1] === true ? row.post_points : null)} projected reserve points; change ${displayPoints(admitted[2] === true ? row.delta : null)}. Legal reserve slots: ${admitted[0] === true ? row.pre_slots ?? 'unavailable' : 'unavailable'} → ${admitted[1] === true ? row.post_slots ?? 'unavailable' : 'unavailable'}.`));
            if (row.conclusion_state !== 'current' || admitted[2] !== true) detail.append(node('small', row.delta == null || admitted[2] !== true ? 'Complete replacement-production comparison unavailable; missing evidence is not zero.' : 'Conditional replacement projection; availability and source evidence remain qualified.'));
            for (const limitation of row.limitations || []) detail.append(node('small', limitation));
          }
          detail.append(node('small', 'One disjoint legal reserve assignment. This does not predict injuries, games played or a complete second starting lineup.'));
        }
        if (strategy.roster_capacity) detail.append(node('p', `Additional configured roster spots to resolve: ${strategy.roster_capacity.additional_spots_to_resolve}. Cut cost is not assumed.`));
        if (strategy.unavailable_dimensions?.length) detail.append(node('small', 'Unavailable: ' + strategy.unavailable_dimensions.join(', ').replaceAll('_', ' ')));
        out.append(detail);
      }
      appendLineupComparisons(out, e, horizons, title, retained);
    }
    }
    const partnerHistory = e.dimensions?.league_partner_context;
    if (partnerHistory) {
      const detail = node('details');
      detail.append(node('summary', (retained ? 'Previous partner context · NOT REVALIDATED' : 'Why this partner?')),
        node('p', decision.partner_summary || partnerHistory.current_benefit || partnerHistory.summary || 'Supported counterparty benefit unavailable.'));
      if (decision.partner_cost || partnerHistory.current_cost) detail.append(node('p', 'Their principal cost: ' + (decision.partner_cost || partnerHistory.current_cost)));
      if (partnerHistory.manager_observations) detail.append(node('p', partnerHistory.manager_observations));
      if (partnerHistory.manager_qualification) detail.append(node('p', partnerHistory.manager_qualification));
      detail.append(node('p', partnerHistory.attribution || 'Historical manager attribution unavailable.'));
      if (retained) detail.append(node('p', 'This retained context is not revalidated against current roster needs or sources.'));
      for (const ref of partnerHistory.references || []) {
        if (/^\/trades\/history\/TRADE-[a-zA-Z0-9_-]+$/.test(ref.url || '')) {
          const link = node('a', `Original trade · ${ref.season || 'season unavailable'} · ${ref.transaction_id}`, 'ds-action');
          link.href = ref.url; const item = node('p'); item.append(link); detail.append(item);
        }
      }
      out.append(detail);
    }
    for (const [which, title] of [['active', 'Your team'], ['partner', 'Their team']]) {
      const diagnostic = e.dimensions?.roster_diagnostics?.sides?.[which];
      if (diagnostic) {
        const detail = node('details');
        detail.append(node('summary', (retained ? 'Previous ' : '') + title + ' roster evidence · ' + (retained ? 'NOT REVALIDATED' : diagnostic.numeric_impact_state || diagnostic.evidence?.conclusion_state || 'unavailable')));
        if (retained) detail.append(node('p', 'Previous package evidence is retained, not revalidated against current sources or availability.'));
        detail.append(node('p', diagnostic.summary || 'Package evidence unavailable.'));
        for (const player of diagnostic.post_lineup_assignments || []) if (player.slot === 'SUPER_FLEX') detail.append(node('p', (retained ? 'Previous post-trade scenario (not current): ' : 'Post-trade conditional lineup: ') + player.name + ' occupies Superflex; this player is counted once.'));
        for (const [phase, evidence, eligibility] of [['Before', diagnostic.pre_evidence, diagnostic.pre_eligibility], ['After', diagnostic.post_evidence, diagnostic.post_eligibility]]) {
          let provenance;
          if (evidence) {
            detail.append(node('p', (retained ? 'Previous ' + phase.toLowerCase() + ' evidence (not current)' : phase) + ': ' + (evidence.conclusion_state || 'unavailable') + ' · Projection evidence ' + (evidence.projection_freshness || ['Unavailable']).join(', ')));
            provenance = sourceProvenance(evidence, e.provenance);
            detail.append(provenance.summary);
          }
          for (const player of eligibility || []) if (player.excluded || player.status !== 'active') detail.append(node('p', phase + ' · ' + player.name + ': ' + player.status + (player.excluded ? ' — excluded from usable cover.' : ' — availability uncertain.')));
          if (provenance) detail.append(provenance.detail);
        }
        out.append(detail);
      }
    }
    if (retained) {
      out.append(node('p', 'Current ownership and execution eligibility are not established by this retained assessment.', 'tw-drawback'));
      if (e.legality?.execution_status) { const detail = node('details'); detail.append(node('summary', 'Previous execution evidence · not current'), node('p', 'Previous execution assessment (not current): ' + e.legality.execution_status)); out.append(detail); }
    }
    if (opportunity) {
      out.append(node('h4', 'Why now · supported context'));
      for (const c of opportunity.why_now?.catalysts || []) out.append(node('p', `${c.side} · ${c.horizon.replaceAll('_', ' ')}: ${displayPoints(catalystDelta(c, decision))}`), node('small', c.limitation));
      if (!opportunity.why_now?.catalysts?.length) out.append(node('p', 'No supported current catalyst is available.'));
      if (opportunity.stable_opportunity_reasons?.length) {
        out.append(node('h4', 'Supported trade fit — not urgency'));
        for (const c of opportunity.stable_opportunity_reasons) out.append(node('p', `${c.side} · ${c.horizon.replaceAll('_', ' ')}: ${displayPoints(catalystDelta(c, decision))}`));
      }
    } else if (e.why_now) out.append(node('h4', 'Why now'), node('p', e.why_now));
    if (e.major_limitations?.length) out.append(node('h4', 'Evidence limitations'), node('p', e.major_limitations.join(', ').replaceAll('_', ' ')));
    if (context) {
      const detail = node('details'); detail.append(node('summary', 'Assessment source & strategy context'));
      detail.append(node('p', 'Assessment strategy: ' + (context.identity?.strategy || 'Use supported competitive window')),
        node('p', 'Counterparty at assessment: ' + (context.identity?.counterparty || 'Unavailable')),
        node('pre', JSON.stringify({identity: context.identity, provenance: e.provenance || null}, null, 2)));
      out.append(detail);
    }
  }
  function strategyAction(out) {
    const button = node('button', 'Choose analysis strategy'); button.type = 'button'; button.dataset.selectStrategy = 'true';
    button.onclick = () => { const detail = root.querySelector('.tw-strategy-detail'); if (detail) detail.open = true; el('trade-strategy').focus(); };
    out.append(button);
  }
  function sourceProvenance(evidence, identity) {
    // Presentation only: canonical qualification remains authoritative.
    const original = [...new Set((evidence.source_observations || []).map(String))];
    const valid = original.map(t => /(?:Z|[+-]\d{2}:\d{2})$/.test(t) ? Date.parse(t) : NaN).filter(t => Number.isFinite(t) && t <= Date.now()).sort((a,b) => a-b);
    const label = t => new Date(t).toISOString().replace('T', ' ').slice(0,16) + ' UTC';
    const parts = ['Projection source observation: ' + (evidence.projection_freshness || ['Unavailable']).join(', '), valid.length + ' distinct source observations'];
    if (valid.length) parts.push(valid.length === 1 ? 'Observed ' + label(valid[0]) : 'Earliest ' + label(valid[0]) + '; latest ' + label(valid[valid.length-1]));
    if (valid.length !== original.length || !original.length) parts.push('Unknown, invalid or future source clocks; provenance is incomplete');
    if (evidence.refresh?.retained_publication) parts.push('Using retained projection evidence; latest refresh did not complete');
    if (evidence.conclusion_state !== 'current') parts.push('Numerical conclusions are ' + (evidence.conclusion_state || 'unavailable'));
    const summary = node('p', parts.join(' · ') + '.', 'diagnostic-source-summary');
    const detail = node('details', '', 'diagnostic-source-provenance');
    detail.append(node('summary', 'Detailed source provenance'), node('p', 'Original source observations; retrieval and refresh attempts do not reset source age. Fresh before 1 hour; Aging from 1 hour; Stale from 6 hours.'));
    const scroll = node('div'); scroll.style.cssText = 'max-height:24rem;overflow:auto;overflow-wrap:anywhere'; scroll.tabIndex = 0; scroll.setAttribute('role','region'); scroll.setAttribute('aria-label','Complete source observations');
    const list = node('ul'); for (const stamp of original) list.append(node('li',stamp));
    scroll.append(original.length ? list : node('p','Source observation times unavailable.')); detail.append(scroll);
    const technical = node('details'); technical.append(node('summary','Source identity and qualifications'));
    const {source_observations, ...qualification} = evidence;
    const facts = node('pre', JSON.stringify({source_identity: identity || 'Unavailable', ...qualification}, null, 2)); facts.style.cssText = 'max-height:24rem;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere';
    technical.append(facts); detail.append(technical);
    return {summary, detail};
  }
  function focusResult() {
    // Focusing a tall container alone can reveal its bottom rather than verdict.
    const result = el('trade-result');
    result.focus({preventScroll: true});
    const verdict = result.querySelector(':scope > .dtos-explanation > p');
    (verdict || result).scrollIntoView({block: verdict ? 'center' : 'start', behavior: 'instant'});
  }
  const newRecommendedObjective = row => (row.workflow || row.proposal.preview_origin_workflow) === 'recommended' && session.originWorkflow !== 'recommended';
  function offerConflict(row) {
    const p = row.proposal;
    if (!team(active) || !team(p.partner_roster_id) || p.assets_sent.some(id => !team(active).assets.some(a => a.asset_id === id)) || p.assets_received.some(id => !team(p.partner_roster_id).assets.some(a => a.asset_id === id))) return 'Ownership changed or unavailable. Your proposal is unchanged; review current assets before adopting.';
    if (p.assets_sent.some(id => session.protectedAssets.includes(id) || session.excludedAssets.includes(id)) || p.assets_received.some(id => session.excludedAssets.includes(id))) return 'This offer violates an exact asset lock. Your proposal is unchanged.';
    if (!newRecommendedObjective(row)) {
      if ((session.requiredOutgoingAsset && !p.assets_sent.includes(session.requiredOutgoingAsset)) || (session.requiredIncomingAsset && !p.assets_received.includes(session.requiredIncomingAsset))) return 'This offer removes the required trade target. Your proposal is unchanged.';
      if (session.requiredIncomingAsset && !team(p.partner_roster_id)?.assets.some(a => a.asset_id === session.requiredIncomingAsset)) return 'The required target belongs to a different owner. Your proposal is unchanged.';
    }
    return null;
  }
  function openOffer(row) {
    reconcileStrategy();
    const conflict = offerConflict(row); if (conflict) return message(conflict, true);
    if (newRecommendedObjective(row)) { session.requiredOutgoingAsset = null; session.requiredIncomingAsset = null; session.originWorkflow = 'recommended'; }
    setPartner(row.proposal.partner_roster_id); selected.sent = [...row.proposal.assets_sent]; selected.received = [...row.proposal.assets_received];
    session.adoptedProposal = {...selected, sent: [...selected.sent], received: [...selected.received]};
    const context = {...assessmentContext(row), stale_reason: 'Package adopted for editing; its assessment has not been revalidated'};
    changed(); session.currentAssessment = context; persist(); review(); showEvaluation(row.evaluation || context.evaluation || {}, row.opportunity || context.opportunity, context); focusResult();
  }
  function previewOffer(row) {
    reconcileStrategy();
    const conflict = offerConflict(row); if (conflict) return message(conflict, true);
    const adjustment = row.balance_adjustment || row.proposal.preview_balance_adjustment;
    if (adjustment && adjustment.market_generation !== workspace.calculator_generation) {
      session.previewProposal = null; persist();
      return message('Market evidence updated. Your current offer and protections are retained; balance again to preview current totals.', true);
    }
    const original = {sent: [...selected.sent], received: [...selected.received], partner: partner()};
    const context = assessmentContext(row);
    row = {...row, proposal: {...row.proposal, preview_context: context}, evaluation: row.evaluation || context.evaluation, exploration: context.exploration, search_result_type: context.search_result_type, opportunity: row.opportunity || context.opportunity};
    retainAssessment();
    session.originalProposal = original; session.previewProposal = {...row.proposal, preview_context: context, preview_balance_adjustment: row.balance_adjustment || row.proposal.preview_balance_adjustment, preview_origin_workflow: row.workflow || row.proposal.preview_origin_workflow || session.originWorkflow}; persist();
    const out = el('trade-result'); out.hidden = false; out.replaceChildren(node('h3', 'Alternative preview'));
    delete out.dataset.assessment;
    const names = ids => ids.map(id => label(asset(id) || {label: id})).join(' + ') || 'None';
    const comparison = adjustment ? node('details') : out;
    if (adjustment) comparison.append(node('summary', 'Compare with original proposal'));
    comparison.append(node('p', 'Original: ' + names(original.sent) + ' → ' + names(original.received)),
      node('p', 'Alternative: ' + names(row.proposal.assets_sent) + ' → ' + names(row.proposal.assets_received)));
    const cost = ids => ids.every(id => asset(id)?.trade_value != null) ? ids.reduce((sum, id) => sum + asset(id).trade_value, 0) : null;
    const oldCost = cost(original.sent), newCost = cost(row.proposal.assets_sent);
    if (original.sent.length && (adjustment || oldCost != null && newCost != null)) comparison.append(node('p', 'Outgoing Market cost: ' + (adjustment ? balanceMarketDisplay(adjustment, 'original').sent : displayMarket(oldCost)) + ' → ' + (adjustment ? balanceMarketDisplay(adjustment, 'suggested').sent : displayMarket(newCost))));
    if (adjustment) {
      for (const [heading, name] of [['Original', 'original'], ['Suggested', 'suggested']]) {
        const shown = balanceMarketDisplay(adjustment, name);
        comparison.append(node('p', `${heading} Market: ${shown.sent} sent / ${shown.received} received · Gap ${shown.gap}`));
      }
      comparison.append(node('p', adjustment.reason), node('small', adjustment.meaning));
    }
    out.append(offerCard(row, true));
    if (adjustment) out.append(comparison);
    contextNotice(out, context, row.proposal);
    const adopt = node('button', 'Adopt alternative'); adopt.type = 'button'; adopt.onclick = () => openOffer(row);
    const keep = node('button', 'Keep original'); keep.type = 'button'; keep.disabled = busy; keep.onclick = () => { session.previewProposal = null; persist(); if (lastOffers) offers(lastOffers, lastOffersIsBalance); else if (session.currentAssessment) showEvaluation(session.currentAssessment.evaluation, session.currentAssessment.opportunity, session.currentAssessment); else message('Original proposal kept.'); };
    out.append(adopt, keep); focusResult();
  }
  function balanceMarketDisplay(balance, name) {
    const m = balance[name] || {}, compatible = Boolean(balance.market_generation) && balance.market_generation === workspace.calculator_generation;
    const full = compatible && [m.sent?.total, m.received?.total, m.absolute_gap].every(value => typeof value === 'number' && Number.isFinite(value)) && m.availability !== 'partial' && m.availability !== 'unavailable';
    const shown = balance.display?.[name] || {};
    const side = name => !compatible ? 'Unavailable · publication context not established' : m[name]?.total != null ? shown[name] ?? displayMarket(m[name].total) : m[name]?.known_subtotal != null ? 'Incomplete · known subtotal ' + displayMarket(m[name].known_subtotal) : 'Unavailable';
    return {sent: side('sent'), received: side('received'), gap: full ? shown.gap ?? displayMarket(m.absolute_gap) : 'Unavailable · incomplete comparison'};
  }
  function balanceOfferCard(row, preview, context) {
    const e = row.evaluation || row.proposal.preview_assessment || {}, balance = row.balance_adjustment || row.proposal.preview_balance_adjustment;
    const card = node('article', null, 'tw-offer tw-balance-offer');
    card.append(node('h3', (balance?.valuation_context?.startsWith('Custom') ? 'Personal valuation' : 'Market') + ' adjustment · preview'));
    const packageLabel = (ids, presented) => ids.map(id => {
      const a = asset(id), source = presented?.find(item => item.asset_id === id);
      return [a ? label(a) : source?.label || id, a?.kind === 'player' ? a.position : null, a?.kind === 'player' ? a.nfl_team : null].filter(Boolean).join(' · ');
    }).join(' + ');
    card.append(node('p', 'You send: ' + packageLabel(row.proposal.assets_sent, row.proposal_presentation?.send), 'tw-offer-package'),
      node('p', 'You receive: ' + packageLabel(row.proposal.assets_received, row.proposal_presentation?.receive), 'tw-offer-package'));
    const shown = balanceMarketDisplay(balance, 'suggested');
    card.append(node('p', `${balance?.valuation_context?.startsWith('Custom') ? 'Your personal valuation' : 'Current Market'}: You send ${shown.sent} / You receive ${shown.received}. Difference: ${shown.gap}.`, 'tw-offer-market'));
    const original = preview ? session.originalProposal || selected : selected;
    const changes = (before, after, side) => {
      const names = ids => ids.slice(0, 2).map(id => label(asset(id) || {label:id})).join(' + ') + (ids.length > 2 ? ' + ' + (ids.length - 2) + ' more' : '');
      const added = after.filter(id => !before.includes(id)), removed = before.filter(id => !after.includes(id));
      return [added.length ? 'Add ' + names(added) + ' to ' + side : '', removed.length ? 'Remove ' + names(removed) + ' from ' + side : ''].filter(Boolean).join('; ');
    };
    card.append(node('p', [changes(original.sent, row.proposal.assets_sent, 'your outgoing package'), changes(original.received, row.proposal.assets_received, 'the assets you receive')].filter(Boolean).join('; '), 'tw-adjustment'));
    const retained = Boolean(contextQualification(context, row.proposal)), decision = decisionPresentation(e);
    if (context.exploration) card.append(node('p', 'Exploratory only · not a qualified bilateral recommendation', 'tw-drawback'));
    card.append(node('p', (retained ? 'Retained assessment · NOT REVALIDATED: ' : e.personalization?.mode === 'custom' ? 'Separate Custom DTOS personal assessment: ' : 'Separate DTOS assessment: ') + finalVerdict(e)));
    if (decision.qualification) card.append(node('p', decision.qualification, 'tw-verdict-qualification'));
    const unfavorable = ['REJECT', 'NOT WORTH IT'].includes(e.recommendation);
    const reason = unfavorable ? 'Closer current Market terms do not make this a recommended trade.' : decision.lineup?.explanation || e.why_you_would_do_it || 'Market balance is separate from strategic fit; no supported positive roster case is established.';
    card.append(node('p', 'Why consider: ' + reason),
      node('p', 'Major drawback: ' + (decision.main_cost || e.major_drawback || 'A supported main cost is unavailable; reevaluate before deciding.'), 'tw-drawback'));
    if (decision.limitation) card.append(node('p', 'Evidence limit: ' + decision.limitation, 'tw-drawback'));
    if (retained) card.append(node('p', 'Prior benefits and drawbacks are not current conclusions. Reevaluate after adoption.', 'tw-drawback'));
    for (const id of [...row.proposal.assets_sent, ...row.proposal.assets_received]) { const protection = lockDetail(id); if (protection) card.append(protection); }
    if (!preview) {
      const button = node('button', 'Preview adjustment', 'tw-next-action primary'); button.type = 'button'; button.onclick = () => previewOffer(row); card.append(button);
    }
    const detail = node('details'); detail.append(node('summary', 'Why this offer · evidence and risks'));
    detail.append(node('p', balance.reason), node('p', balance.meaning), node('p', 'Counterparty: ' + (decision.partner_summary || e.counterparty_summary || e.why_they_would_do_it || 'Supported partner context unavailable.')));
    if (e.explanation_html) {
      const parsed = parsedExplanation(e); detail.append(...parsed.body.childNodes);
    } else {
      for (const text of [decision.summary || e.why_you_would_do_it, e.dominant_reason, ...(e.major_risks || []), ...(e.major_limitations || [])]) if (text) detail.append(node('p', text));
      appendLineupComparisons(detail, e, decision.lineup_comparisons, 'Your team', true);
      appendLineupComparisons(detail, e, decision.partner_lineup_comparisons, 'Their team', true);
    }
    card.append(detail, node('small', 'Current values, not trade-date grades. Preview before adopting.'));
    return card;
  }
  function offerCard(row, preview = false) {
    const context = assessmentContext(row);
    assessedOfferContexts.set(row, context);
    const card = node('article', null, 'tw-offer');
    const e = row.evaluation || row.proposal.preview_assessment || {};
    const balance = row.balance_adjustment || row.proposal.preview_balance_adjustment;
    if (balance) return balanceOfferCard(row, preview, context);
    if (row.exploration) card.append(node('p', 'Exploratory only · ' + row.search_result_type + ' · not a qualified bilateral recommendation', 'tw-drawback'));
    if (row.exploration) {
      const counterpart = e.dimensions?.counterparty_plausibility;
      if (counterpart) card.append(node('p', 'Counterparty support: ' + counterpart.assessment + ' · ' + (counterpart.reason_codes || []).map(code => code.replaceAll('_', ' ')).join('; ')));
    }
    card.append(node('h3', (e.personalization?.mode === 'custom' ? 'Custom DTOS · ' : '') + finalVerdict(e)));
    if (e.personalization?.mode === 'custom') card.append(node('p', 'Neutral DTOS: ' + (e.neutral_assessment?.recommendation || 'Unavailable') + ' · Market fairness and opponent evidence remain separate.', 'tw-verdict-qualification'));
    const matches = row.personal_preference_matches;
    if (matches?.targets_received?.length) card.append(node('p', 'Matches your saved target preference: ' + matches.targets_received.map(id => label(asset(id) || {label:id})).join(' + ')));
    if (matches?.avoid_received?.length) card.append(node('p', 'Includes an asset you prefer to avoid. This soft preference has not changed the trade facts.', 'tw-drawback'));
    const decision = decisionPresentation(e);
    if (decision.qualification) card.append(node('p', decision.qualification, 'tw-verdict-qualification'));
    if (row.repair_type) card.append(node('p', row.repair_type));
    if (row.adjustment_evidence?.concept === 'strictly_lower_canonical_outgoing_market_cost') {
      const cost = row.adjustment_evidence;
      card.append(node('p', `Outgoing Market cost: ${cost.current_outgoing_cost} → ${cost.alternative_outgoing_cost} (${cost.market_cost_reduction} lower).`));
    }
    const sentRows = row.proposal_presentation?.send || row.proposal.assets_sent.map(id => ({label: label(asset(id) || {label:id})}));
    const receivedRows = row.proposal_presentation?.receive || row.proposal.assets_received.map(id => ({label: label(asset(id) || {label:id})}));
    card.append(node('p', 'You send: ' + sentRows.map(a => a.label).join(' + ')), node('p', 'You receive: ' + receivedRows.map(a => a.label).join(' + ')),
      node('p', 'Why this helps me: ' + (decision.summary || e.why_you_would_do_it || e.dominant_reason || 'Review the supported evidence.')),
      node('p', 'Major drawback: ' + (decision.main_cost || e.major_drawback || e.major_risks?.join('; ').replaceAll('_', ' ') || e.major_limitations?.join('; ').replaceAll('_', ' ') || (row.proposal.preview_context?.restored ? 'Unavailable in retained context. Reevaluate for supported costs.' : 'No material drawback identified in available evidence.')), 'tw-drawback'),
      node('p', 'Counterparty: ' + (decision.partner_summary || e.counterparty_summary || e.why_they_would_do_it || e.dimensions?.counterparty_plausibility?.explanation || 'Review the separate bilateral evidence.')));
    for (const id of [...row.proposal.assets_sent, ...row.proposal.assets_received]) { const protection = lockDetail(id); if (protection) card.append(protection); }
    const intent = e.dimensions?.strategic_fit?.active?.manager_strategy?.strategy;
    if (intent) card.append(node('p', 'Strategy: ' + intent));
    const history = e.dimensions?.counterparty_plausibility?.manager_history?.disclosure;
    if (history) card.append(node('small', history));
    if (!e.explanation_html) {
      const detail = node('details'); detail.append(node('summary', 'Supported assessment evidence' + (e.dimensions?.confidence?.assessment ? ' · Confidence ' + e.dimensions.confidence.assessment : '')));
      for (const [key, dim] of Object.entries(e.dimensions || {})) if (dim?.assessment) detail.append(node('p', (dim.label || key.replaceAll('_', ' ')) + ': ' + dim.assessment), node('small', key === 'counterparty_plausibility' && decision.lineup_rationale_verified?.partner === false ? decision.partner_summary : dim.explanation));
      for (const reason of [...(e.major_risks || []), ...(e.major_limitations || [])]) detail.append(node('p', reason.replaceAll('_', ' ')));
      appendLineupComparisons(detail, e, decision.lineup_comparisons, 'Your team', true);
      appendLineupComparisons(detail, e, decision.partner_lineup_comparisons, 'Their team', true);
      if (e.provenance?.evaluation_id) detail.append(node('small', 'Original assessment: ' + e.provenance.evaluation_id));
      if (detail.childElementCount > 1) card.append(detail);
    }
    if (!preview) { const b = node('button', 'Open editable offer: preview'); b.type = 'button'; b.className = 'tw-next-action primary'; b.onclick = () => previewOffer(row); card.append(b); }
    if (e.explanation_html) {
      const detail = node('details'); detail.append(node('summary', 'Why this offer · evidence and risks'));
      const parsed = parsedExplanation(e);
      detail.append(...parsed.body.childNodes); card.append(detail);
    }
    if (row.variants?.length && !preview) {
      const detail = node('details'); detail.append(node('summary', 'Related package variants'));
      for (const variant of row.variants) detail.append(offerCard(variant)); card.append(detail);
    }
    return card;
  }
  function searchDetails(body, out) {
    if (body.other_trade_ideas?.length) {
      const section = node('section'); section.setAttribute('aria-label', 'Other trade ideas');
      section.append(node('h3', 'Other trade ideas'), node('p', 'These change your requested incoming target. Your original trade stays intact unless you explicitly preview and adopt one.'));
      for (const row of body.other_trade_ideas) section.append(offerCard(row));
      out.append(section);
    }
    if (body.exploratory_results?.length) {
      const section = node('section'); section.setAttribute('aria-label', 'Supported alternatives · not recommended');
      section.append(node('h3', 'Supported alternatives · not recommended'), node('p', 'These evaluated offers have costs or unfavorable tradeoffs. Their original recommendation labels apply. Preview before deciding.'));
      for (const row of body.exploratory_results) section.append(offerCard(row));
      out.append(section);
    }

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
      const detail = node('details', null, 'tw-near-misses'); detail.append(node('summary', 'Evaluated near misses'));
      for (const row of body.near_misses) {
        const p = row.proposal;
        if (!p || !row.evaluation) continue; // A near miss must be an assessed package.
        const names = (presented, ids) => presented?.length ? presented.map(a => a.label).join(' + ') : (ids || []).map(id => label(asset(id) || {label: id})).join(' + ');
        detail.append(node('p', names(row.proposal_presentation?.send, p.assets_sent) + ' → ' + names(row.proposal_presentation?.receive, p.assets_received)),
          node('p', row.conflict_explanation || row.blocker_type + ': ' + (row.blockers || []).join(', ').replaceAll('_', ' ')));
        for (const id of row.blocking_asset_ids || []) detail.append(node('p', 'Blocking asset: ' + label(asset(id) || {label: id}) + ' · ' + id));
        if (row.smallest_optional_relaxation) detail.append(node('p', (row.blocker_type === 'MISSING REQUIRED EVIDENCE' ? 'Evidence limit: ' : 'Optional change: ') + row.smallest_optional_relaxation));
        if (row.evaluation?.decision_context?.strategy?.selection_required) strategyAction(detail);
        if (row.blocker_type === 'MISSING REQUIRED EVIDENCE') {
          const market = node('a', 'Review current Market evidence'); market.href = '/market';
          detail.append(market);
        }
      }
      out.append(detail);
    }
    if (body.search_evidence) { const detail = node('details'); detail.append(node('summary', 'Technical search details'), node('pre', JSON.stringify(body.search_evidence, null, 2))); out.append(detail); }
  }
  function offers(body, isBalance = false) {
    delete el('trade-result').dataset.assessment;
    lastOffers = body; lastOffersIsBalance = isBalance;
    if (isBalance) el('calculator-balance-status').after(el('trade-result'));
    if (flow === 'recommended' && body.workflow === 'recommended') {
      displayedFamilies = [...(body.results || []), ...(body.exploratory_results || [])].map(row => row.family_id);
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
      const refineLink = node('a', 'Refine returns · optional', 'ds-action'); refineLink.href = '#shop-refinements'; out.append(refineLink);
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
    if (personalRevisionStale) return personalChangedNotice();
    if (busy || !workspace) return;
    if (path === 'generate' && entryBlocked) return;
    if (path === 'generate' && ((flow === 'shop' && !session.requiredOutgoingAsset && selected.sent.length !== 1) || (flow === 'trade_for' && !session.requiredIncomingAsset && selected.received.length !== 1))) return message('Choose one target asset for this search. Multi-asset proposals can still be evaluated directly.', true);
    if (path === 'generate' && flow === 'shop') {
      session.requiredOutgoingAsset = session.requiredOutgoingAsset || selected.sent[0]; session.requiredIncomingAsset = null; session.originWorkflow = 'shop';
      if (session.shopScopeAsset !== session.requiredOutgoingAsset) {
        session.shopScopeAsset = session.requiredOutgoingAsset; session.shopSearchPartner = 0; session.shopPreference = 'best_overall'; session.shopPosition = 'QB';
        el('trade-partner').value = ''; el('shop-preference').value = session.shopPreference; el('shop-position').value = session.shopPosition;
      }
      extra = {...extra, partner_roster_id: session.shopSearchPartner, asset_id: session.requiredOutgoingAsset,
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
    if (path === 'balance' || path === 'evaluate') retainAssessment();
    busy = true; const started = revision, startedRun = ++runSequence;
    const controller = new AbortController(); activeRequest = controller;
    let timedOut = false;
    const timeout = controller ? setTimeout(() => { timedOut = true; controller.abort(); }, path === 'balance' ? 45000 : 120000) : null;
    if (path === 'balance') { balanceRequest = controller; balanceStatus('Finding balancing options… Asset changes pause until this search finishes. Your offer stays intact.'); }
    // Freeze the exact request, including binding, anchors and locks. A retry
    // must never reinterpret it under a newer navigation or strategy intent.
    const requestPayload = {...payload(), ...extra};
    if (path === 'generate') searchStatus('Searching supported trades… Your offer stays intact.', 'loading', started, startedRun);
    paint();
    message(path === 'balance' ? 'Checking owned, lock-respecting Market adjustments… Your original stays intact.' : path === 'generate' ? 'Searching supported bilateral options… Your proposal stays intact.' : path === 'assist' ? 'Checking revised offers… Your original proposal stays intact.' : 'Evaluating your proposal…');
    if (path === 'evaluate') el('trade-result').dataset.assessmentState = 'evaluating';
    try {
      let body;
      try { body = await post(path, requestPayload, controller?.signal); } catch (error) {
        if (error.code !== 'canonical_evidence_changed' || started !== revision) throw error;
        message('Evidence refreshed. Checking the same request once more… Your proposal stays intact.');
        body = await post(path, requestPayload, controller?.signal);
      }
      reconcileStrategy();
      if (started !== revision) return;
      observeEvidence(body);
      if (path === 'evaluate' && !body.evaluation?.recommendation && !body.evaluation?.explanation_html) throw new Error('Evaluation incomplete. Retained assessment is not revalidated; try Reevaluate Trade again.');
      for (const id of body.constraints?.protected_assets || []) addLock('protectedAssets', id);
      for (const id of body.constraints?.excluded_assets || []) addLock('excludedAssets', id);
      if (path === 'assist') {
        const lostTarget = body.results?.some(row => selected.received.some(id => !row.proposal.assets_received.includes(id)));
        const youngerChange = (extra.instruction || '').toLowerCase().includes('younger') && !['shop', 'trade_for'].includes(session.originWorkflow);
        const invalidPreservation = body.results?.length && !youngerChange && extra.repair_mode !== 'ALTERNATIVE_TARGET' && (body.target_preserved !== true || lostTarget);
        if (body.requested_mode !== extra.repair_mode || body.returned_modes?.some(mode => mode !== extra.repair_mode) || invalidPreservation) throw new Error('DTOS rejected a mismatched repair mode. Your proposal is unchanged.');
      }
      if (path === 'balance') balanceStatus(body.results?.length ? 'Balancing options ready. Preview before adopting.' : body.other_trade_ideas?.length ? 'No supported target-preserving option. Other trade ideas are separate below; your offer is unchanged.' : 'No balancing options returned. Your offer is unchanged.', started, startedRun);
      if (path === 'generate') searchStatus(body.results?.length ? 'Trade options ready. Review before adopting.' : body.exploratory_results?.length ? 'No recommended options. Supported alternatives are available below.' : 'No credible options found in this search. Review the search details below.', 'complete', started, startedRun);
      if (path === 'evaluate') {
        const context = assessmentContext({...body, evaluation: body.evaluation});
        context.attempt_state = body.assessment_source_identity ? body.evaluation?.assessment_state?.state || 'fresh_incomplete' : 'fresh_incomplete';
        if (context.attempt_state === 'fresh_incomplete' && session.currentAssessment) {
          // The new attempt owns current supported findings. Keep at most one
          // genuine previous assessment, separately qualified and never current.
          context.previous_assessment = restoreContext(session.currentAssessment.previous_assessment || session.currentAssessment, false);
        }
        session.currentAssessment = context; persist(); review(); showEvaluation(body.evaluation, null, context); el('trade-result').after(el('trade-balancing'));
      } else offers(body, path === 'balance');
    } catch (error) { if (started === revision) {
      const feedback = timedOut ? (path === 'balance' ? 'Balancing' : 'Search') + ' timed out. Your offer is unchanged. Try again.' : path === 'balance' && error instanceof TypeError ? 'Balancing could not connect. Your offer is unchanged. Try again.' : error.message;
      if (path === 'balance') balanceStatus(feedback, started, startedRun);
      if (path === 'generate') searchStatus(feedback, 'error', started, startedRun);
      if (path === 'evaluate' && session.currentAssessment) {
        staleAssessment(error.code === 'ownership_changed' ? 'Current ownership blocker: ' + feedback : 'Reevaluation failed or incomplete: ' + feedback);
        showEvaluation(session.currentAssessment.evaluation, session.currentAssessment.opportunity, session.currentAssessment);
        return;
      }
      message(feedback, true);
      if (error.personalRecovery) {
        const link = node('a', 'Review affected Custom Rankings assets'); link.href = '/account/my-dtos#personal-compatibility';
        el('trade-result').append(link);
      }
      if (path === 'evaluate') { el('trade-result').dataset.assessmentState = 'failed'; reevaluateAction(el('trade-result')); }
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
        if (activeRequest === controller) activeRequest = null;
        busy = false; paint();
        if (started === revision && !el('trade-result').hidden && !(flow === 'shop' && path === 'generate')) focusResult();
      }
    }
  }
  el('trade-view').onclick = review; el('trade-tray-view').onclick = review; el('trade-edit').onclick = edit;
  el('trade-run').onclick = () => run('evaluate'); el('trade-find').onclick = () => run('generate');
  el('trade-balance-offer').onclick = () => run('balance');
  if (marketEditor) {
    el('calculator-protect').onclick = () => { el('trade-assist').hidden = false; el('trade-constraint-asset').focus(); };
    el('calculator-lock').onclick = () => { if (busy) return; const exact = el('trade-constraint-asset').value; if (!exact) return message('Choose an exact owned player or pick to protect.', true); addLock('protectedAssets', exact); revision++; clearBalancePreview(); persist(); paint(); message('Exact outgoing protection added. Original offer retained; remove this asset if it is currently outgoing.'); };
  }
  function clearDraft() {
    cancelBalance(); revision++; runSequence++; busy = false;
    selected.sent = []; selected.received = []; selected.partner = 0;
    for (const key of ['originalProposal','previewProposal','adoptedProposal','currentAssessment','requiredOutgoingAsset','requiredIncomingAsset','shopScopeAsset']) session[key] = null;
    session.protectedAssets = []; session.excludedAssets = []; session.overrideSavedProtections = []; session.adjustmentConstraints = {};
    session.originWorkflow = 'create'; session.shopSearchPartner = 0;
    session.shopPreference = 'best_overall'; session.shopPosition = 'QB';
    session.resetGeneration = String(Date.now()) + ':' + Math.random().toString(36).slice(2);
    excludedFamilies.clear(); displayedFamilies = []; searchExhausted = false;
    lastOffers = null; lastOffersIsBalance = false; balanceFeedback = null; searchFeedback = null;
    el('trade-instruction').value = ''; el('trade-constraint-asset').value = '';
    el('trade-result').replaceChildren(); el('trade-result').hidden = true;
    el('trade-assist').hidden = true; el('trade-review').hidden = true;
    setPartner(0); syncLocks(); persist(); paint();
  }
  el('trade-clear-package').onclick = () => {
    if (!workspace) return;
    cancelBalance(); revision++; runSequence++;
    selected.sent = session.requiredOutgoingAsset ? [session.requiredOutgoingAsset] : [];
    selected.received = session.requiredIncomingAsset ? [session.requiredIncomingAsset] : [];
    session.originalProposal = null; session.previewProposal = null; session.adoptedProposal = null; session.currentAssessment = null;
    lastOffers = null; lastOffersIsBalance = false;
    el('trade-result').replaceChildren(); el('trade-result').hidden = true;
    persist(); paint();
  };
  el('trade-start-new').onclick = () => {
    if (!workspace) return;
    const hasDraft = selected.sent.length || selected.received.length || partner() || session.requiredOutgoingAsset || session.requiredIncomingAsset || session.currentAssessment || session.previewProposal || session.protectedAssets.length || session.excludedAssets.length || Object.keys(session.adjustmentConstraints).length;
    if (hasDraft && !confirm('Start a new trade? This clears this league’s current package, target, previews and temporary protections. Your selected strategy and other league drafts stay saved.')) return;
    try { sessionStorage.removeItem(storageKey()); } catch (_) { message('The saved draft could not be cleared. Allow browser session storage and try again; your strategy is unchanged.', true); return; }
    clearDraft();
    // Replace the cleared entry; Back cannot resurrect its old Shop/Trade For objective.
    location.replace('/trades/create?front_office=' + active);
  };
  el('trade-build-own').onclick = () => {
    if (!workspace) return;
    cancelBalance(); if (busy) return;
    // The destination gets a new draft. Leave this document and its history
    // snapshot intact so a BF-cache return can resume the original Shop scope.
    persist(false, {...session, requiredOutgoingAsset: null, requiredIncomingAsset: null, originWorkflow: 'create',
      currentProposal: {sent: [], received: [], partner: 0}, originalProposal: null, adoptedProposal: null, previewProposal: null, currentAssessment: null});
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
  el('trade-partner').onchange = () => { if (flow === 'shop') { session.shopSearchPartner = Number(el('trade-partner').value || 0); if (!selected.received.length) selected.partner = session.shopSearchPartner; changed(); if (session.requiredOutgoingAsset) run('generate'); return; } if (session.requiredIncomingAsset) { el('trade-partner').value = String(partner()); return message('The required target stays with its actual owner. Choose Build My Own to change the objective.', true); } setPartner(el('trade-partner').value); selected.received = []; changed(); if (flow === 'shop' && session.requiredOutgoingAsset) run('generate'); };
  function writeStrategyIntent() {
    if (!workspace || !window.dtosStrategy) return;
    const retained = window.dtosStrategy.set(workspace.workspace_context, el('trade-strategy').value);
    let feedback = el('trade-strategy-feedback');
    if (!feedback) { feedback = node('p', '', 'ds-inline-feedback'); feedback.id = 'trade-strategy-feedback'; feedback.setAttribute('role', 'status'); el('trade-strategy').after(feedback); }
    feedback.textContent = retained ? '' : 'Strategy could not be retained for fresh navigation: browser session storage is unavailable or full.';
  }
  function reconcileStrategy() {
    if (!workspace || !window.dtosStrategy || departed) return;
    const intent = window.dtosStrategy.get(workspace.workspace_context);
    if (intent === el('trade-strategy').value) return;
    el('trade-strategy').value = intent;
    cancelBalance(); revision++; runSequence++;
    lastOffers = null; lastOffersIsBalance = false; excludedFamilies.clear(); searchExhausted = false;
    if (session.previewProposal?.preview_context) {
      session.previewProposal.preview_context.restored = true;
      session.previewProposal.preview_context.stale_reason = 'Strategy changed in another tab';
    }
    if (session.currentAssessment) staleAssessment('Strategy changed in another tab');
    else if (session.previewProposal) previewOffer({proposal: session.previewProposal});
    root.querySelectorAll('[data-assessment-strategy]').forEach(summary => { summary.textContent = 'Assessment strategy: ' + (summary.dataset.assessmentStrategy || 'Use supported competitive window') + ' · Current selected strategy: ' + (intent || 'Use supported competitive window'); });
    root.querySelectorAll('.tw-offer').forEach(card => {
      if (!card.querySelector('[data-offer-stale]')) { const notice = node('p', 'Retained offer assessment · not revalidated after strategy change. Preview retains its original strategy; reevaluate after adoption.', 'tw-drawback'); notice.dataset.offerStale = 'true'; card.prepend(notice); }
    });
    if (workspace) paint();
  }
  addEventListener('focus', reconcileStrategy);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) reconcileStrategy(); });
  el('trade-strategy').onchange = () => { writeStrategyIntent(); el('trade-evaluation-retained')?.remove(); session.currentAssessment = null; cancelBalance(); revision++; session.previewProposal = null; lastOffers = null; lastOffersIsBalance = false; if (workspace) paint(); excludedFamilies.clear(); searchExhausted = false; el('trade-result').hidden = true; if (flow === 'shop') searchStatus('Not started for this strategy. Find Shop returns to search again; missing projection coverage may still limit results.', 'not_started'); persist(); };
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
      if (workspace && history.state?.dtosTrade?.binding === workspace.workspace_context.binding) {
        const retained = JSON.parse(sessionStorage.getItem(storageKey()) || 'null');
        if (retained?.resetGeneration && retained.resetGeneration !== session.resetGeneration) {
          location.replace('/trades/create?front_office=' + active); return;
        }
        reconcileStrategy();
        if (session.currentAssessment) { session.currentAssessment = restoreContext(session.currentAssessment); showEvaluation(session.currentAssessment.evaluation || {}, session.currentAssessment.opportunity, session.currentAssessment); }
        if (session.previewProposal) { if (session.previewProposal.preview_context) session.previewProposal.preview_context = restoreContext(session.previewProposal.preview_context); previewOffer({proposal: session.previewProposal}); }
        persist();
      }
    }
  });
  matchMedia('(max-width:760px)').addEventListener('change', () => { if (workspace) paint(); });
  fetch('/api/trades/workspace?front_office=' + active + (marketEditor ? '&mode=calculator' : ''), {credentials: 'same-origin'}).then(async response => { if (!response.ok) throw new Error('Unable to load this authorized workspace.'); return response.json(); }).then(data => {
    workspace = data;
    if (data.personalization) {
      const p = data.personalization;
      const savedMode = restoredDraft()?.valuationMode;
      valuationMode = new URL(location.href).searchParams.has('home_offer') ? 'neutral' : (savedMode || p.mode || 'neutral');
      if (valuationMode === 'custom' && (!(p.revision > 0) || p.available !== true)) valuationMode = 'neutral';
      const panel = node('section', null, 'card tw-valuation-mode');
      const label = node('label', 'Valuation mode'); label.htmlFor = 'trade-valuation-mode';
      const select = node('select'); select.id = 'trade-valuation-mode';
      for (const [value, text] of [['neutral', 'Neutral DTOS'], ['custom', 'Custom DTOS']]) { const option = node('option', text); option.value = value; option.disabled = value === 'custom' && (!(p.revision > 0) || p.available !== true); select.append(option); }
      select.value = valuationMode;
      const needsReview = p.revision > 0 && p.compatibility_issues?.length;
      const edit = node('a', needsReview ? 'Review affected Custom Rankings assets' : 'Edit My DTOS rankings');
      edit.href = needsReview ? '/account/my-dtos#personal-compatibility' : '/account/my-dtos';
      panel.append(label, select, node('p', 'Neutral Market and Sleeper lineup facts stay unchanged. Custom DTOS uses your saved ranking values for your decision.'), edit);
      if (p.personal_partial_available) panel.append(node('p', (p.limitations || []).join(' ') || `${p.personal_value_count} saved assets have verified Custom values. Only packages using verified values can receive a Custom assessment. Other assets and your saved order remain intact.`, 'muted'));
      if (p.available !== true) panel.append(node('p', !(p.revision > 0)
        ? 'Create Custom Rankings in My DTOS to use Custom Trade. Neutral DTOS is available now.'
        : (p.limitations || []).join(' ') || 'Saved Custom Rankings need compatible Market prices. Open My DTOS to retry; Neutral Trade remains available.', 'muted'));
      root.prepend(panel);
      select.onchange = () => {
        activeRequest?.abort(); activeRequest = null; balanceRequest = null; revision++; runSequence++; busy = false;
        valuationMode = select.value; clearBalancePreview(); lastOffers = null; excludedFamilies.clear(); searchExhausted = false;
        if (session.currentAssessment) staleAssessment('Valuation mode changed. Reevaluate this exact proposal.');
        el('trade-result').hidden = true;
        persist(); paint(); message('Valuation mode changed. Your exact offer is unchanged; reevaluate or run an explicit search.');
      };
    }
    if (window.dtosStrategy) el('trade-strategy').value = window.dtosStrategy.get(data.workspace_context);
    pickerOptions(el('trade-constraint-asset'), team(active)?.assets || []);
    if (flow === 'recommended') {
      el('trade-find').textContent = 'Discover Recommended Trades';
      el('recommendation-refresh').onclick = () => {
        if (busy) return;
        for (const family of displayedFamilies) if (excludedFamilies.size < 256) excludedFamilies.add(family);
        run('generate');
      };
      el('recommendation-filter').onchange = () => { excludedFamilies.clear(); searchExhausted = false; changed(); searchStatus('Filter changed. Discover supported opportunities under the selected context.', 'ready'); };
    }
    if (flow === 'shop') {
      pickerOptions(el('shop-protected'), team(active)?.assets || []);
      el('shop-preference').onchange = () => { session.shopPreference = el('shop-preference').value; changed(); if (session.requiredOutgoingAsset) run('generate'); };
      el('shop-position').onchange = () => { session.shopPosition = el('shop-position').value; changed(); if (session.requiredOutgoingAsset) run('generate'); };
      el('shop-protected').onchange = () => { session.protectedAssets = Array.from(el('shop-protected').selectedOptions, option => option.value); changed(); if (session.requiredOutgoingAsset) run('generate'); };
    }
    // Independent league drafts are retained within the bounded workspace cache.
    for (const t of data.teams) if (t.roster_id !== active) { const option = node('option', t.team_name); option.value = t.roster_id; el('trade-partner').append(option); }
    try {
      let saved = restoredDraft();
      if (saved?.endedAtHome) { clearDraft(); saved = null; }
      const proposal = saved?.currentProposal || (saved?.selected ? {...saved.selected, partner: saved.partner} : null);
      if (proposal && (team(proposal.partner) || Number(proposal.partner) === 0) && Array.isArray(proposal.sent) && Array.isArray(proposal.received)) {
        setPartner(proposal.partner); selected.sent = [...proposal.sent]; selected.received = [...proposal.received];
        for (const key of ['resetGeneration', 'originalProposal', 'previewProposal', 'adoptedProposal', 'requiredOutgoingAsset', 'requiredIncomingAsset', 'adjustmentConstraints', 'originWorkflow', 'shopSearchPartner', 'shopScopeAsset', 'shopPreference', 'shopPosition', 'currentAssessment']) if (saved.schema === 2 && key in saved) session[key] = saved[key];
        session.currentAssessment = session.currentAssessment ? restoreContext(session.currentAssessment) : null;
        if (session.previewProposal?.preview_context) session.previewProposal.preview_context = restoreContext(session.previewProposal.preview_context);
        // Older drafts retained only a string summary: it is prior context,
        // never a freshly validated assessment or an inferred endorsement.
        if (session.previewProposal && !session.previewProposal.preview_context) session.previewProposal.preview_context = {...assessmentContext({proposal: session.previewProposal}), restored: true, stale_reason: 'Legacy preview qualification and supporting evidence were not retained'};
        for (const key of ['protectedAssets', 'excludedAssets', 'overrideSavedProtections']) if (Array.isArray(saved[key])) session[key] = [...new Set(saved[key])];
        if (saved.strategy && Array.from(el('trade-strategy').options).some(o => o.value === saved.strategy) && !window.dtosStrategy?.has(data.workspace_context)) {
          window.dtosStrategy?.set(data.workspace_context, saved.strategy);
          el('trade-strategy').value = saved.strategy;
        }
        if (saved.ownership !== data.workspace_context.ownership_generation) message('Ownership has changed. Your proposal is retained for review; evaluation will identify any assets that moved.', true);
      }
    } catch (_) { /* No persisted draft is required. */ }
    let startTargetSearch = false;
    const preload = root.dataset.preloadAsset;
    if (preload) {
      const owner = data.teams.find(t => t.assets.some(a => a.asset_id === preload));
      if (!owner || (flow === 'shop' && owner.roster_id !== active) || (flow === 'trade_for' && owner.roster_id === active)) {
        entryBlocked = true; message('This asset is not currently owned by the required franchise. Review current ownership or choose another Trade Center entry.', true);
      } else {
        const freshNavigation = !['reload', 'back_forward'].includes(performance.getEntriesByType('navigation')[0]?.type);
        const compatible = session.originWorkflow === flow && (flow === 'shop'
          ? session.requiredOutgoingAsset === preload && !session.requiredIncomingAsset && selected.sent.includes(preload)
          : session.requiredIncomingAsset === preload && !session.requiredOutgoingAsset && selected.received.includes(preload));
        startTargetSearch = freshNavigation && (flow !== 'shop' || !compatible);
        if (!compatible) {
          const replaced = selected.sent.length || selected.received.length;
          // Explicit entry targets outrank unrelated restored intent. Exact
          // locks survive within this authorized binding and remain enforced.
          revision++;
          selected.sent = []; selected.received = []; setPartner(0);
          session.originalProposal = null; session.previewProposal = null; session.adoptedProposal = null; session.currentAssessment = null;
          session.adjustmentConstraints = {}; session.originWorkflow = flow;
          session.requiredOutgoingAsset = flow === 'shop' ? preload : null;
          session.requiredIncomingAsset = flow === 'trade_for' ? preload : null;
          if (flow === 'shop') selected.sent = [preload];
          else { setPartner(owner.roster_id); selected.received = [preload]; }
          if (replaced) { const notice = node('p', (flow === 'shop' ? 'Now shopping ' : 'Now pursuing ') + label(asset(preload)) + '. The previous package was cleared. Exact protections are retained.', 'ds-inline-feedback'); notice.id = 'trade-entry-feedback'; el('trade-target').after(notice); }
        } else if (flow === 'trade_for') setPartner(owner.roster_id);
        if (flow === 'shop') {
          if (!compatible) { session.shopSearchPartner = 0; session.shopPreference = 'best_overall'; session.shopPosition = 'QB'; }
          session.shopScopeAsset = preload;
          // Query refinements represent new navigation only. Reload/history
          // restores the controls actually chosen, not stale URL defaults.
          if (freshNavigation) {
            const query = new URL(location.href).searchParams;
            const explicitPartner = query.get('partner_roster_id'), explicitPreference = query.get('shop_preference');
            if (explicitPartner !== null && (explicitPartner === '0' || (team(Number(explicitPartner)) && Number(explicitPartner) !== active))) { session.shopSearchPartner = Number(explicitPartner); startTargetSearch = true; }
            if (explicitPreference !== null && Array.from(el('shop-preference').options).some(o => o.value === explicitPreference)) { session.shopPreference = explicitPreference; startTargetSearch = true; }
          }
        }
      }
    }
    if (flow === 'trade_for' && session.requiredIncomingAsset) side = 'sent';
    el('trade-instruction').value = session.adjustmentConstraints.instruction || '';
    el('trade-constraint-asset').value = session.adjustmentConstraints.constraint_asset_id || '';
    if (flow === 'shop') {
      if (!team(session.shopSearchPartner) || session.shopSearchPartner === active) session.shopSearchPartner = 0;
      el('trade-partner').value = session.shopSearchPartner ? String(session.shopSearchPartner) : '';
      if (Array.from(el('shop-preference').options).some(o => o.value === session.shopPreference)) el('shop-preference').value = session.shopPreference;
      if (Array.from(el('shop-position').options).some(o => o.value === session.shopPosition)) el('shop-position').value = session.shopPosition;
    }
    if (window.dtosStrategy) el('trade-strategy').value = window.dtosStrategy.get(data.workspace_context);
    syncLocks(); el('trade-find').hidden = flow === 'create'; persist(); paint();
    if (data.projection_evidence) latestEvidence.projection_generation = data.projection_evidence.generation;
    if (flow === 'recommended') searchStatus('Ready to discover supported opportunities.', 'ready');
    if (flow === 'shop') { el('trade-find').textContent = 'Find Shop returns'; searchStatus('Not started. Find Shop returns searches the selected scope; strategy alone cannot resolve missing projection coverage.', 'not_started'); }
    if (session.currentAssessment && !entryBlocked) showEvaluation(session.currentAssessment.evaluation || {}, session.currentAssessment.opportunity, session.currentAssessment);
    if (session.previewProposal && !entryBlocked) previewOffer({proposal: session.previewProposal});
    const homeOffer = new URL(location.href).searchParams.get('home_offer');
    if (homeOffer && !entryBlocked && !departed && (!['reload', 'back_forward'].includes(performance.getEntriesByType('navigation')[0]?.type) || (!session.adoptedProposal && !session.previewProposal && history.state?.dtosHomeOffer !== homeOffer))) {
      const navigationRevision = revision;
      const requestedStrategy = el('trade-strategy').value;
      const query = new URLSearchParams({front_office: active, offer: homeOffer,
        protected: JSON.stringify(session.protectedAssets), excluded: JSON.stringify(session.excludedAssets)});
      fetch('/api/trades/home-opportunities?' + query, {credentials: 'same-origin'}).then(async response => {
        if (!response.ok) throw new Error('This Home idea expired or its evidence, strategy or protections changed. Your draft is unchanged. Find current ideas on Home.');
        const row = await response.json();
        reconcileStrategy();
        if (departed || revision !== navigationRevision || requestedStrategy !== el('trade-strategy').value) return;
        try { history.replaceState({...history.state, dtosHomeOffer: homeOffer}, ''); } catch (_) { /* Navigation state may be unavailable. */ }
        previewOffer(row);
      }).catch(error => { if (!departed && revision === navigationRevision) message(error.message, true); });
    }
    if (startTargetSearch && !entryBlocked && !departed) { run('generate'); if (flow === 'shop') searchStatus('Searching automatically for this newly selected asset… Your proposal stays intact.', 'loading'); }
  }).catch(error => message(error.message, true));
})();
