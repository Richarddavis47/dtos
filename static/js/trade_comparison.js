/* Bounded presentation of two completed assessments. No HTTP or evaluation. */
(() => {
  'use strict';
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
    function offer(entry, index, comparison) {
      const out = node('article', null, 'tw-comparison-offer'); out.dataset.comparisonSlot = String(index + 1);
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
        out.append(node('p', (side === 'active' ? 'Your team: ' : 'Their team: ') + (depth[side] || 'Reserve-depth evidence unavailable.')));
        const spots = capacity[side];
        out.append(node('p', (side === 'active' ? 'Your' : 'Their') + ' additional configured roster spots to resolve: ' +
          (number(spots) ? spots + '. No cut is assumed.' : 'Unknown; roster feasibility is not inferred.')));
      }
      out.append(node('p', 'Main cost or risk: ' + s.cost, 'tw-drawback'),
        node('p', 'Their case: ' + s.partnerReason), node('p', 'Conditions: ' + s.conditions, 'tw-drawback'));
      if (s.limitation) out.append(node('p', 'Evidence limit: ' + s.limitation, 'tw-drawback'));
      const disclosure = node('details'); disclosure.append(node('summary', 'Original assessment · both teams and evidence limits'));
      disclosure.append(node('small', 'Captured ' + (entry.context?.identity?.captured_at || 'time unavailable') + '. Values and conclusions belong to this offer’s original assessment.'));
      details(entry, disclosure); out.append(disclosure);
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
  const api = {compatibility, sameScope, wellFormed, create};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else globalThis.DTOSOfferComparison = api;
})();
