/* Bounded presentation of two completed assessments. No HTTP or evaluation. */
(() => {
  'use strict';
  function customerText(value) {
    return String(value || '').replaceAll('compatible prepared publication', 'league data for this week')
      .replaceAll('Canonical Market', 'Market value').replaceAll('canonical Market', 'Market value')
      .replaceAll('disjoint reserve cover', 'different eligible backups')
      .replaceAll('No legitimate bilateral construction clears the current constraints.', 'No offers met the requirements for both teams in this search.')
      .replaceAll('Useful replacement production declines without a material supported starter gain or Market compensation.', 'Projected points from eligible backups fall without a meaningful starting-lineup gain or Market value to offset the loss.')
      .replaceAll('Useful replacement production changes', 'Projected points from eligible backups change')
      .replaceAll('legal-replacement production falls', 'projected points from eligible backups fall')
      .replaceAll('legal-replacement production improves', 'projected points from eligible backups improve')
      .replaceAll('legal-replacement production declines', 'projected points from eligible backups decline')
      .replaceAll('legal-replacement production', 'projected points from eligible backups')
      .replaceAll('bilateral recommendation', 'recommendation for both teams');
  }
  const number = value => typeof value === 'number' && Number.isFinite(value);
  const known = value => (typeof value === 'string' && value.length > 0) || number(value);
  const sameScope = (entry, scope) => entry?.schema === 1 && scope?.binding &&
    entry.scope?.binding === scope.binding && entry.scope.league === scope.league && entry.scope.roster === scope.roster;
  const wellFormed = entry => entry && typeof entry.id === 'string' && entry.id.length > 0 &&
    typeof entry.summary === 'object' && entry.summary !== null && !Array.isArray(entry.summary) &&
    typeof entry.summary.verdict === 'string' && ['neutral', 'custom'].includes(entry.summary.mode) &&
    ['sent', 'received'].every(side => Array.isArray(entry.assets?.[side]) && entry.assets[side].length <= 32 &&
      entry.assets[side].every(row => typeof row?.id === 'string' && row.id.length <= 256 && typeof row.label === 'string' && row.label.length <= 512));
  const keys = {
    league: 'league', roster: 'franchise', ownership: 'roster baseline', lineup: 'prepared roster baseline',
    season: 'season', week: 'projection week', scoring: 'scoring context', projection: 'projection generation', provider: 'projection source'
  };
  function compatibility(entries, current) {
    const stop = (state, reason) => ({supported: false, state, reason});
    if (!entries.length || entries.length > 2) return stop('missing', 'Choose one or two completed offers.');
    for (const entry of entries) {
      if (!sameScope(entry, current.scope)) return stop('incompatible', 'The account, league or franchise context differs.');
      const identity = entry.baseline || {};
      if (Object.keys(keys).some(key => !known(identity[key]))) return stop('unknown', 'The recorded league, roster, week, scoring or generation identity is incomplete.');
      if (identity.league !== entry.scope.league || identity.roster !== entry.scope.roster)
        return stop('incompatible', 'The assessment provenance names another league or franchise.');
      if (entry.context?.stale_reason || entry.summary?.stale) return stop('stale', entry.context?.stale_reason || entry.summary.stale);
      if (identity.ownership !== current.ownership) return stop('stale', 'Roster ownership changed since the recorded assessment.');
      if (!known(current.projection) || identity.projection !== current.projection) return stop('stale', 'The compatible current projection generation is missing or has changed.');
      for (const key of ['lineup', 'season', 'week', 'scoring', 'provider']) {
        if (!known(current[key])) return stop('unknown', 'The prepared ' + keys[key] + ' is not currently established.');
        if (identity[key] !== current[key]) return stop('stale', 'The prepared ' + keys[key] + ' changed since this offer was assessed.');
      }
      if (entry.context?.identity?.market !== current.market) return stop('stale', 'Market evidence changed since this assessment.');
      if (current.personalStale && entry.summary?.mode === 'custom') return stop('stale', 'The saved personal ranking revision is no longer verified.');
      if (entry.summary?.mode === 'custom' && ['revision', 'market', 'baseline', 'method'].some(key =>
          !known(entry.summary.personalContext?.[key]) || !known(current.personalContext?.[key]) ||
          entry.summary.personalContext[key] !== current.personalContext[key]))
        return stop('stale', 'The Custom ranking revision, valuation method or compatible personal publication changed or is unverified. Original personal values remain recorded evidence only.');
      const inputs = entry.context?.evaluation?.provenance?.inputs || {};
      if (Object.entries(current.observed || {}).some(([key, value]) => known(value) && known(inputs[key]) && value !== inputs[key]))
        return stop('stale', 'Prepared source evidence changed since an offer was evaluated.');
    }
    const first = entries[0];
    if (entries.some(entry => Object.keys(keys).some(key => entry.baseline[key] !== first.baseline[key]))) {
      const key = Object.keys(keys).find(key => entries.some(entry => entry.baseline[key] !== first.baseline[key]));
      return stop('incompatible', 'Offers use different ' + keys[key] + '; they cannot share a lineup comparison.');
    }
    if (entries.every(entry => number(entry.summary?.lineup?.pre_total)) &&
        entries.some(entry => entry.summary.lineup.pre_total !== first.summary.lineup.pre_total))
      return stop('incompatible', 'The recorded before-trade lineup totals differ; keeping the roster is not the same baseline.');
    for (const entry of entries) {
      const row = entry.summary?.lineup || {};
      if (row.state !== 'supported' || ![row.pre_total, row.post_total, row.delta].every(number))
        return {...stop('incomplete', 'A complete, nonprovisional legal-lineup comparison is not supported for every offer. Supported individual effects remain separate; missing evidence is not zero.'), shared_identity: true};
      if (!Array.isArray(row.weeks) || row.weeks.length !== 1 || String(row.weeks[0]) !== String(entry.baseline.week) ||
          Math.abs(row.post_total - row.pre_total - row.delta) > 1e-8)
        return stop('unknown', 'The recorded lineup totals, week and change cannot be reconciled.');
    }
    const retained = entries.some(entry => entry.retained || entry.context?.restored);
    return {supported: true, state: retained ? 'retained' : 'recorded',
      reason: 'Same recorded roster baseline, scoring, week and projection generation. ' +
        (retained ? 'Retained evidence · NOT REVALIDATED. ' : '') +
        'These are projections at assessment time, not a new evaluation or a guarantee of current availability.',
      baseline: first.summary.lineup.pre_total, week: first.baseline.week, season: first.baseline.season};
  }

  function readCapital(record, scope) {
    try {
      if (!record || !Array.isArray(record.parts) || record.parts.length > 8 ||
          !record.parts.every(p => typeof p === 'string' && p.length <= 1400)) return null;
      const text = record.parts.join('');
      if (text.length !== record.characters || text.length > 10000) return null;
      const r = JSON.parse(text);
      if (r.schema !== 1 || r.league !== scope.league || r.roster !== scope.roster) return null;
      const valid = rows => Array.isArray(rows) && rows.length <= 2048 && rows.every(k =>
        Array.isArray(k) && k.length === 3 && k.every(n => Number.isSafeInteger(n) && n > 0));
      if (!valid(r.sent || []) || !valid(r.received || []) || !valid(r.before || [])) return null;
      const keys = rows => rows.map(k => k.join(':'));
      if (new Set(keys((r.sent || []).concat(r.received || []))).size !== (r.sent || []).length + (r.received || []).length ||
          new Set(keys(r.before || [])).size !== (r.before || []).length) return null;
      if (r.complete && (!r.generation || !Array.isArray(r.seasons) || !Number.isSafeInteger(r.rounds) || r.rounds < 1 || r.rounds > 20 ||
          r.seasons.some(y => !Number.isSafeInteger(y)) || r.before.concat(r.sent, r.received).some(k => !r.seasons.includes(k[0]) || k[1] > r.rounds) ||
          r.sent.some(k => !keys(r.before).includes(k.join(':'))) || r.received.some(k => keys(r.before).includes(k.join(':'))))) return null;
      return r;
    } catch (_) { return null; }
  }
  function capitalView(record, node, scope, retained = true, keep = false) {
    const box = node('section', null, 'tw-draft-capital'); box.setAttribute('aria-label', 'Your draft capital after this trade');
    box.append(node('h5', keep ? 'Your draft capital · keep the roster' : 'Your draft capital after this trade'));
    const r = readCapital(record, scope);
    if (!r) { box.append(node('p', 'Recorded compatible pick inventory was not retained. Remaining totals are unknown; today’s inventory is not substituted.')); return box; }
    box.append(node('small', retained ? 'Recorded ownership · NOT REVALIDATED. No current inventory is substituted.' : 'Ownership recorded with this assessment. Only retained seasons and configured rounds are covered.'));
    const label = k => `${k[0]} round ${k[1]} · Original franchise: ${r.names?.[String(k[2])] || k[2]}${k[2] === r.roster ? ' · Your own pick' : ' · Acquired franchise pick'} · Exact ${k[0]}-R${k[1]}-${k[2]}`;
    const sent = keep ? [] : r.sent || [], received = keep ? [] : r.received || [];
    if (r.complete) {
      const after = r.before.filter(k => !sent.some(s => s.join(':') === k.join(':'))).concat(received);
      for (const year of r.seasons) {
        const lines = [];
        for (let round = 1; round <= r.rounds; round++) {
          const before = r.before.filter(k => k[0] === year && k[1] === round), next = after.filter(k => k[0] === year && k[1] === round);
          lines.push(`R${round}: ${before.length} → ${next.length}` + (round === 1 ? ` (own firsts ${before.filter(k => k[2] === r.roster).length} → ${next.filter(k => k[2] === r.roster).length}; other firsts ${before.filter(k => k[2] !== r.roster).length} → ${next.filter(k => k[2] !== r.roster).length})` : ''));
        }
        box.append(node('p', year + ' · ' + lines.join(' · ')));
      }
      const details = node('details'); details.append(node('summary', 'Exact owned picks · before and after'));
      for (const [title, rows] of [['Before', r.before], ['After', after]]) {
        details.append(node('h6', title)); const list = node('ul'); for (const k of rows) list.append(node('li', label(k))); details.append(list);
      }
      box.append(details);
    } else box.append(node('p', r.reason || 'Complete inventory unavailable; remaining totals are unknown.'));
    const moves = node('details'); moves.append(node('summary', 'Exact picks sent and acquired'));
    for (const [title, rows] of [['Sent', sent], ['Acquired', received]]) {
      moves.append(node('h6', title)); const list = node('ul'); for (const k of rows) list.append(node('li', label(k)));
      if (!rows.length) list.append(node('li', r.invalid ? 'Unverified movement' : 'None in this recorded exchange')); moves.append(list);
    }
    box.append(moves); return box;
  }

  function acquisitionView(out, record, node, market, retained = false, compact = false) {
    if (!record) return;
    const roles = record.roles || [], cost = record.cost || {};
    const labels = [];
    if (roles.includes('best_fit')) labels.push('Best-supported fit found');
    if (roles.includes('lowest_cost')) labels.push('Lowest-cost supported offer found');
    out.append(node('p', labels.join(' · ') || 'Different supported construction', 'tw-acquisition-role'));
    const detail = node('details'); detail.append(node('summary', 'Acquisition cost evidence · Neutral Market'));
    if (retained) out.append(node('small', 'Roles and costs belong to the recorded search, not a new assessment.'));
    if (cost.availability === 'full' && [cost.outgoing, cost.incoming, cost.net_received_minus_sent, cost.extra_received_value].every(number)) {
      out.append(node('p', 'Gross outgoing Neutral Market cost: ' + market(cost.outgoing)));
      detail.append(node('p', 'All assets received: ' + market(cost.incoming) + ' · Net Market received minus sent: ' + market(cost.net_received_minus_sent) + '.'));
      out.append(node('p', cost.extra_received_asset_ids?.length
        ? 'Includes additional incoming assets worth ' + market(cost.extra_received_value) + ' beyond the exact target. Packages with different extras are not equivalent purchases.'
        : 'No additional incoming assets beyond the exact target.'));
    } else out.append(node('p', cost.reason || 'Complete compatible Neutral Market cost is unknown; this offer cannot be selected as lowest-cost.', 'tw-drawback'));
    detail.append(node('small', 'Among ' + record.eligible_assessed + ' eligible assessed offers; ' + record.cost_comparable_assessed + ' have complete comparable Neutral Market costs. ' +
      (record.lowest_cost_ties > 1 ? 'Lowest cost tied; existing fit ordering breaks the tie. ' : '') +
      'Costs do not determine the original verdict.'));
    out.append(node('small', 'Bounded search, not a global minimum, asking price or guarantee of acceptance. Lower cost does not establish a better trade.'));
    if (!compact) out.append(detail);
  }
  function create(options) {
    const {node, points, market, panel, tray, getEntries, setEntries, environment, details} = options;
    let returnFocus = null, returnScroll = 0;
    const entries = () => getEntries().filter(row => wellFormed(row) && sameScope(row, environment().scope)).slice(0, 2);
    const button = (text, action) => { const b = node('button', text); b.type = 'button'; b.onclick = action; return b; };
    const signed = value => number(value) ? (value > 0 ? '+' : '') + points(value) : 'Unavailable';
    function save(rows) { setEntries(rows); refresh(); }
    function price(side, label) {
      return label + ': ' + (side?.availability === 'full' && number(side.sent) && number(side.received)
        ? market(side.sent) + ' sent / ' + market(side.received) + ' received'
        : 'Incomplete or unavailable; no complete package value inferred.');
    }
    function recordedPeriod(recorded) {
      let row = recorded;
      if (typeof row === 'string') { try { row = JSON.parse(row); } catch (_) { row = null; } }
      return row && typeof row === 'object' ? row : null;
    }
    function partnerCase(entry) {
      const row = recordedPeriod(entry.context?.evaluation?.decision_context?.partner_lineup_comparisons?.current_week);
      const supported = row && ['supported', 'provisional'].includes(row.state) && number(row.delta) && Array.isArray(row.weeks) && row.weeks.length;
      return 'Their case: Fit is an inference, not confirmed willingness. ' + (supported
        ? 'Recorded week ' + row.weeks.join(', ') + ' lineup change: ' + signed(row.delta) + ' projected points' + (row.state === 'provisional' ? ' · provisional' : '') + '.'
        : 'Their projected lineup change is unverified; no production benefit is assumed.');
    }
    function participationCautions(entry) {
      const e = entry.context?.evaluation || {}, cautions = new Set();
      const material = /\b(?:OUT|IR|PUP|SUSPENDED|INACTIVE|RETIRED)\b|Bye \/ no scheduled game/i;
      const diagnostics = e.dimensions?.roster_diagnostics || {};
      const period = known(diagnostics.week) ? 'Week ' + diagnostics.week : 'week not recorded';
      for (const [side, title] of [['active', 'Your team'], ['partner', 'Their team']]) {
        const rows = diagnostics.sides?.[side]?.post_eligibility;
        for (const row of (Array.isArray(rows) ? rows : []).slice(0, 64)) {
          if (row.name && material.test(String(row.status || '') + ' ' + String(row.reason || '')))
            cautions.add(title + ' after trade · ' + period + ': ' + row.name + ' · ' + (row.reason || String(row.status).toUpperCase()));
        }
      }
      // Older records may retain a named warning only in the original prose.
      // Keep that warning visible; never infer a player's participation state.
      const source = [entry.summary.limitation, entry.summary.conditions, ...(e.major_risks || [])];
      for (const text of source) for (const sentence of String(text || '').split(/\n|(?<=[.!?])\s+/))
        if (material.test(sentence) && !entry.summary.cost?.includes(sentence)) cautions.add('Recorded warning: ' + sentence);
      return [...cautions];
    }
    function offer(entry, index, comparison) {
      const out = node('article', null, 'tw-comparison-offer'); out.dataset.comparisonSlot = String(index + 1);
      const capital = node('details'); capital.append(node('summary', 'Draft capital · picks before and after'), capitalView(entry.context?.draft_capital_record, node, environment().scope, true));
      acquisitionView(out, entry.summary.acquisition, node, market, entry.retained || entry.context?.restored);
      const s = entry.summary, depth = s.depth || {}, capacity = s.capacity || {};
      out.append(node('h4', 'Offer ' + (index + 1) + ' · ' + s.verdict),
        node('p', 'Counterparty: ' + s.partner), node('p', 'Assessment strategy: ' + (s.strategy || 'No selected goal')));
      if (entry.retained || entry.context?.restored) out.append(node('p', 'Retained assessment · NOT REVALIDATED', 'tw-drawback'));
      if (entry.context?.exploration) out.append(node('p', 'Exploratory only · not a qualified recommendation', 'tw-drawback'));
      const individual = comparison.supported ? comparison : comparison.shared_identity ? compatibility([entry], environment()) : null;
      if (individual?.supported) out.append(node('p', (comparison.supported ? '' : 'Supported individual effect · not a complete two-offer comparison. ') +
        'Week ' + individual.week + ' lineup change vs keeping the roster: ' + signed(s.lineup.delta) + ' projected points.', 'tw-comparison-gain'),
        node('p', points(individual.baseline) + ' → ' + points(s.lineup.post_total) + ' optimal-lineup points.'));
      else out.append(node('p', 'Shared lineup comparison withheld. Original results below remain separate recorded evidence.', 'tw-drawback'));
      for (const [side, title] of [['sent', 'You send'], ['received', 'You receive']]) {
        out.append(node('h5', title)); const list = node('ol'); list.setAttribute('aria-label', title + ' in original asset order');
        for (const item of entry.assets[side]) {
          const row = node('li', item.label); row.append(node('small', 'Exact asset: ' + item.id)); list.append(row);
        }
        out.append(list);
      }
      out.append(node('p', price(s.neutral, 'Neutral Market at evaluation')));
      if (s.mode === 'custom') out.append(node('p', price(s.personal, 'Your Custom values · ' + (s.methodLabel || 'method not retained'))),
        node('small', 'Personal value does not establish the counterparty’s willingness or change Neutral Market.'));
      out.append(node('h5', 'Depth and roster consequences'));
      for (const side of ['active', 'partner']) {
        out.append(node('p', (side === 'active' ? 'Your team: ' : 'Their team: ') + customerText(depth[side] || 'Reserve-depth evidence unavailable.')));
        const spots = capacity[side];
        out.append(node('p', (side === 'active' ? 'Your' : 'Their') + ' additional configured roster spots to resolve: ' +
          (number(spots) ? spots + '. No cut is assumed.' : 'Unknown; roster feasibility is not inferred.')));
      }
      out.append(node('p', 'Main cost or risk: ' + customerText(s.cost), 'tw-drawback'), node('p', partnerCase(entry), 'tw-comparison-partner'));
      const cautions = participationCautions(entry);
      if (cautions.length) out.append(node('p', 'Availability to review: ' + cautions.join(' '), 'tw-comparison-risk-summary tw-drawback'));
      const decision = entry.context?.evaluation?.decision_context || {};
      const provisional = s.lineup?.state === 'provisional' || recordedPeriod(decision.lineup_comparisons?.current_week)?.state === 'provisional' || /\bprovisional\b/i.test(String(decision.qualification || ''));
      if (s.limitation || provisional) out.append(node('p', (provisional ? 'Provisional assessment. ' : '') + 'Some availability or coverage remains unverified. Review the original assessment for the affected evidence.', 'tw-comparison-qualification tw-drawback'));
      const disclosure = node('details'); disclosure.append(node('summary', 'Original assessment · both teams and evidence limits'));
      disclosure.append(node('small', 'Captured ' + (entry.context?.identity?.captured_at || 'time unavailable') + '. Values and conclusions belong to this offer’s original assessment.'));
      disclosure.append(node('p', 'Recorded cost: ' + s.cost), node('p', 'Their original case: ' + s.partnerReason));
      if (s.conditions !== entry.context?.evaluation?.decision_context?.decision_conditions)
        disclosure.append(node('p', 'Conditions: ' + s.conditions, 'tw-drawback'));
      if (s.limitation) disclosure.append(node('p', 'Evidence limit: ' + s.limitation, 'tw-drawback'));
      details(entry, disclosure); out.append(disclosure);
      out.append(capital);
      out.append(button('Remove offer ' + (index + 1), () => save(entries().filter((_, i) => i !== index))));
      return out;
    }
    function close() {
      panel.hidden = true;
      window.scrollTo({top: returnScroll, behavior: 'instant'});
      const focus = returnFocus?.isConnected ? returnFocus : tray.querySelector('button');
      focus?.focus({preventScroll: true});
    }
    function render() {
      const rows = entries(), result = compatibility(rows, environment()); panel.replaceChildren();
      const heading = node('h3', 'Compare with keeping your roster'); heading.tabIndex = -1; heading.id = 'trade-comparison-heading';
      panel.append(heading, button('Return to my offer or draft', close), node('p', result.reason, result.supported ? '' : 'tw-drawback'));
      panel.dataset.comparisonState = result.state;
      panel.append(node('p', 'No search, reevaluation or refresh runs here. Each original decision and counterparty case remains attached to its own offer.'));
      panel.append(node('small', 'Analytical optimal lineups are separate from your submitted Sleeper lineup, which this view never changes.'));
      if (rows.length === 2 && (rows[0].summary.mode !== rows[1].summary.mode || rows[0].summary.method !== rows[1].summary.method))
        panel.append(node('p', 'Valuation modes or methods differ. Personal and Neutral values are separate; this view does not choose a preferred deal.'));
      const grid = node('div', null, 'tw-comparison-grid'), keep = node('section', null, 'tw-comparison-keep');
      keep.append(node('h4', 'Keep the roster · no trade'), node('p', 'No players or picks exchanged. Existing depth and roster spots are unchanged by a trade.'));
      keep.append(node('p', result.supported ? 'Season ' + result.season + ' · week ' + result.week + ': ' + points(result.baseline) + ' recorded optimal-lineup points; 0.00 trade-related change.' : 'A shared supported lineup total is unavailable. No zero projection is inferred.'));
      const capitals = rows.map(row => readCapital(row.context?.draft_capital_record, environment().scope));
      if (capitals.length && capitals.every(c => c?.complete && c.generation === capitals[0].generation))
        { const capital = node('details'); capital.append(node('summary', 'Draft capital · keep the roster'), capitalView(rows[0].context.draft_capital_record, node, environment().scope, true, true)); keep.append(capital); }
      else keep.append(node('p', 'A shared recorded draft-capital baseline is unavailable; each offer’s supported inventory stays separate.'));
      grid.append(keep); rows.forEach((row, i) => grid.append(offer(row, i, result))); panel.append(grid);
      if (!rows.length) panel.append(node('p', 'Add a completed assessment from this Trade workspace. Your draft has not changed.'));
    }
    function open() {
      returnFocus = document.activeElement; returnScroll = window.scrollY;
      render(); panel.hidden = false;
      panel.querySelector('h3').focus({preventScroll: true}); panel.scrollIntoView({block: 'start'});
    }
    function refresh() {
      const rows = entries(); tray.hidden = !rows.length; tray.replaceChildren();
      tray.append(node('span', rows.length + ' of 2 offers selected. '), button('Compare selected offers', open));
      if (!panel.hidden) {
        const focused = panel.contains(document.activeElement);
        render(); if (focused) panel.querySelector('h3').focus({preventScroll: true});
      }
    }
    function add(entry, source) {
      if (!wellFormed(entry) || !sameScope(entry, environment().scope) || JSON.stringify(entry).length > 100000) return false;
      const nearby = () => {
        source.parentElement.querySelector('.tw-compare-open')?.remove();
        const action = button('Open comparison', open); action.className = 'tw-compare-open'; source.after(action);
      };
      const rows = entries();
      if (rows.some(row => row.id === entry.id)) { open(); return true; }
      if (rows.length < 2) { save([...rows, entry]); nearby(); return true; }
      source.parentElement.querySelector('.tw-comparison-replace')?.remove();
      const choices = node('div', null, 'tw-comparison-replace'); choices.setAttribute('role', 'group'); choices.setAttribute('aria-label', 'Replace selected comparison offer');
      choices.append(node('p', 'Two offers are selected. Choose which to replace; your draft stays unchanged.'));
      for (let i = 0; i < 2; i++) choices.append(button('Replace offer ' + (i + 1), () => { save(rows.map((row, n) => n === i ? entry : row)); choices.remove(); nearby(); }));
      choices.append(button('Keep both selected offers', () => choices.remove())); source.after(choices); return true;
    }
    refresh();
    return {add, refresh};
  }
  const api = {customerText, acquisitionView, compatibility, sameScope, wellFormed, create, readCapital, capitalView};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else globalThis.DTOSOfferComparison = api;
})();
