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
      if (!response.ok) throw new Error('Your team brief could not be loaded. Open Trade or try again.');
      const body = await response.json();
      if (run !== revision || departed || (before && before !== identity())) return;
      if (body.workspace_context.roster_id !== rid || (context && body.workspace_context.binding !== context.binding)) {
        cards.replaceChildren(); find.disabled = true; metadata = null;
        invalidated = true; displayedIdentity = null; reload.hidden = false;
        status.textContent = 'Your active league or franchise changed. Reload Home to see its opportunities.';
        root.dataset.presentation = 'empty'; root.dataset.state = 'context_changed'; return;
      }
      const initial = !context; context = body.workspace_context; metadata = body;
      if (body.strategy !== (window.dtosStrategy.get(context) || '')) { cards.replaceChildren(); return load(); }
      if (initial && (locks().protected_assets.length || locks().excluded_assets.length)) return load();
      const html = body.brief_html ?? body.html;
      if (cards.innerHTML !== html) cards.innerHTML = html;
      displayedIdentity = identity(); // Escaped same-origin canonical presentation, no scoring here.
      status.textContent = body.count ? 'Recently completed search · matches the current team and data. These offers have not been submitted.' : body.retained ? (body.reason || 'No supported opportunities in this bounded search.') : 'No current matching search has been completed. Find Trade Ideas when ready.';
      if (!body.source_identity) status.textContent = 'Trade prices are unavailable or changing. Your roster facts are still shown separately. Review My Team or try again shortly.';
      else if (!body.brief_count && 'brief_count' in body) status.textContent = 'No actionable insight qualifies from the available team data. Review My Team or choose Find Trade Ideas; this does not mean no useful trades exist.';
      root.dataset.state = body.state;
      root.dataset.presentation = body.brief_count ? 'prepared' : 'empty';
    } catch (error) { if (run === revision && !departed && error.name !== 'AbortError') {
      cards.replaceChildren(); metadata = null; displayedIdentity = null;
      root.dataset.presentation = 'error'; status.textContent = error.message;
    } }
  }
  find.onclick = async () => {
    if (invalidated) return;
    if (!context || !metadata?.source_identity) return load();
    const run = ++revision, before = identity(), frozen = {...locks()};
    request?.abort(); request = new AbortController(); find.disabled = true;
    status.textContent = 'Searching trade ideas… Home and your draft stay available.'; root.dataset.state = 'loading'; root.dataset.presentation = 'loading';
    const controller = request;
    const timeout = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch('/api/trades/generate', {method:'POST', credentials:'same-origin', signal:request.signal,
        headers:{'Content-Type':'application/json','X-CSRF-Token':metadata.csrf_token},
        body:JSON.stringify({workflow:'recommended', active_roster_id:rid, partner_roster_id:0, strategy:window.dtosStrategy.get(context) || null,
          workspace_context:context, home_source_identity:metadata.source_identity, ...frozen})});
      if (!response.ok) {
        const failure = await response.json().catch(() => ({}));
        const detail = failure.detail || failure;
        const deferred = detail.code === 'trade_capacity_deferred';
        const error = new Error(deferred
          ? 'Trade search is waiting for capacity. Your draft is intact. Try Find Trade Ideas later.'
          : 'Trade search did not finish. Your draft is intact. Try again or open Recommended Trades.');
        error.presentation = deferred ? 'capacity_deferred' : 'failed';
        throw error;
      }
      if (run !== revision || departed || before !== identity()) return;
      await load();
    } catch (error) { if (run === revision && !departed) {
      root.dataset.state = error.name === 'AbortError' ? 'interrupted' : (error.presentation || 'failed');
      root.dataset.presentation = error.presentation === 'capacity_deferred' ? 'deferred' : 'error';
      status.textContent = (error.name === 'AbortError' ? 'Search interrupted or timed out. Your draft is intact; retry explicitly when ready.' : error.message)
        + (cards.children.length ? ' Earlier results remain below; this search did not update them.' : ' No new search result is available.');
    } }
    finally { clearTimeout(timeout); if (run === revision && !invalidated) find.disabled = false; }
  };
  reload.onclick = () => location.reload();
  addEventListener('pagehide', () => { departed = true; revision++; request?.abort(); });
  addEventListener('pageshow', () => { if (departed) { departed = false; load(); } });
  addEventListener('focus', () => { if (!invalidated && context && (!find.disabled || metadata?.strategy !== window.dtosStrategy.get(context))) load(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && context && !invalidated) load(); });
  load();
})();
