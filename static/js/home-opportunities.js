/* Read completed, scoped canonical searches. Discovery is an explicit action. */
(() => {
  'use strict';
  const root = document.getElementById('home-opportunities');
  if (!root) return;
  const status = document.getElementById('home-opportunity-status'), cards = document.getElementById('home-opportunity-cards');
  const find = document.getElementById('home-find-ideas'), rid = Number(root.dataset.frontOffice);
  const reload = document.getElementById('home-reload-opportunities');
  let context, metadata, displayedIdentity, revision = 0, request, departed = false, invalidated = false;
  const locks = () => {
    try { const saved = JSON.parse(sessionStorage.getItem('dtos-trade-workspace:' + context.binding) || '{}');
      if (saved.endedAtHome) return {protected_assets: [], excluded_assets: []};
      return {protected_assets: saved.protectedAssets || [], excluded_assets: saved.excludedAssets || []};
    } catch (_) { return {protected_assets: [], excluded_assets: []}; }
  };
  const identity = () => JSON.stringify([context?.binding, context && window.dtosStrategy.get(context), context && locks()]);
  const query = () => { const c = context ? locks() : {protected_assets: [], excluded_assets: []};
    return new URLSearchParams({front_office: rid, protected: JSON.stringify(c.protected_assets), excluded: JSON.stringify(c.excluded_assets)}); };
  async function load() {
    if (departed || invalidated) return;
    const run = ++revision; request?.abort(); request = new AbortController(); find.disabled = false;
    if (displayedIdentity && displayedIdentity !== identity()) cards.replaceChildren();
    const before = context && identity();
    try {
      const response = await fetch('/api/trades/home-opportunities?' + query(), {credentials:'same-origin', signal:request.signal});
      if (!response.ok) throw new Error('Prepared opportunities are unavailable. Explore Trades or try again.');
      const body = await response.json();
      if (run !== revision || departed || (before && before !== identity())) return;
      if (body.workspace_context.roster_id !== rid || (context && body.workspace_context.binding !== context.binding)) {
        cards.replaceChildren(); find.disabled = true; metadata = null;
        invalidated = true; displayedIdentity = null; reload.hidden = false;
        status.textContent = 'Your active league or franchise changed. Reload Home to see its opportunities.';
        root.dataset.state = 'context_changed'; return;
      }
      const initial = !context; context = body.workspace_context; metadata = body;
      if (body.strategy !== (window.dtosStrategy.get(context) || '')) { cards.replaceChildren(); return load(); }
      if (initial && (locks().protected_assets.length || locks().excluded_assets.length)) return load();
      const html = body.brief_html ?? body.html;
      if (cards.innerHTML !== html) cards.innerHTML = html;
      displayedIdentity = identity(); // Escaped same-origin canonical presentation, no scoring here.
      status.textContent = body.count ? 'Recently completed search · current matching evidence. Hypothetical offers, not submitted trades.' : body.retained ? (body.reason || 'No supported opportunities in this bounded search.') : 'No current matching search is prepared. Find Trade Ideas when ready.';
      if (!body.source_identity) status.textContent = 'Trade pricing is unavailable or changing. Prepared roster facts remain separate. Review My Team or try again shortly.';
      else if (!body.brief_count && 'brief_count' in body) status.textContent = 'No actionable insight qualifies in the prepared evidence. Review My Team or explicitly Find Trade Ideas; this is not proof that no opportunities exist.';
      root.dataset.state = body.state;
    } catch (error) { if (run === revision && !departed && error.name !== 'AbortError') {
      cards.replaceChildren(); metadata = null; displayedIdentity = null;
      status.textContent = error.message;
    } }
  }
  find.onclick = async () => {
    if (invalidated) return;
    if (!context || !metadata?.source_identity) return load();
    const run = ++revision, before = identity(), frozen = {...locks()};
    request?.abort(); request = new AbortController(); find.disabled = true;
    status.textContent = 'Searching supported opportunities… Home and your draft stay available.'; root.dataset.state = 'loading';
    const controller = request;
    const timeout = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch('/api/trades/generate', {method:'POST', credentials:'same-origin', signal:request.signal,
        headers:{'Content-Type':'application/json','X-CSRF-Token':metadata.csrf_token},
        body:JSON.stringify({workflow:'recommended', active_roster_id:rid, partner_roster_id:0, strategy:window.dtosStrategy.get(context) || null,
          workspace_context:context, home_source_identity:metadata.source_identity, ...frozen})});
      if (!response.ok) throw new Error('Search unavailable or evidence changed. Your draft is intact. Try again or Explore more trades.');
      if (run !== revision || departed || before !== identity()) return;
      await load();
    } catch (error) { if (run === revision && !departed) status.textContent = error.name === 'AbortError' ? 'Search interrupted or timed out. Try again; your draft is intact.' : error.message; }
    finally { clearTimeout(timeout); if (run === revision && !invalidated) find.disabled = false; }
  };
  reload.onclick = () => location.reload();
  addEventListener('pagehide', () => { departed = true; revision++; request?.abort(); });
  addEventListener('pageshow', () => { if (departed) { departed = false; load(); } });
  addEventListener('focus', () => { if (!invalidated && context && (!find.disabled || metadata?.strategy !== window.dtosStrategy.get(context))) load(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && context && !invalidated) load(); });
  load();
})();
