/* Session cookie shares only explicit intent between tabs. Never assets or locks. */
(() => {
  const name = 'dtos_strategy', allowed = ['', 'WIN NOW', 'RETOOL', 'REBUILD'];
  function read(context) {
    try {
      const raw = document.cookie.split('; ').find(row => row.startsWith(name + '='))?.slice(name.length + 1);
      const saved = raw ? JSON.parse(atob(raw.replaceAll('-', '+').replaceAll('_', '/'))) : null;
      return saved?.scope === context.strategy_scope && Array.isArray(saved.rows) && saved.rows.length <= 64 && saved.rows.every(row => Array.isArray(row) && row.length === 2 && typeof row[0] === 'string' && row[0].length < 80 && allowed.includes(row[1])) ? saved : {scope: context.strategy_scope, rows: []};
    } catch (_) { return {scope: context.strategy_scope, rows: []}; }
  }
  function get(context) {
    const value = read(context).rows.find(row => row[0] === `${context.league_id}:${context.roster_id}`)?.[1];
    return allowed.includes(value) ? value : '';
  }
  function set(context, value) {
    if (!allowed.includes(value)) return false;
    const saved = read(context), key = `${context.league_id}:${context.roster_id}`;
    const rows = saved.rows.filter(row => row[0] !== key);
    if (rows.length >= 64) return false;
    rows.push([key, value]); saved.rows = rows;
    const encoded = btoa(JSON.stringify(saved)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
    if (encoded.length > 3800) return false;
    document.cookie = `${name}=${encoded}; Path=/; SameSite=Strict${location.protocol === 'https:' ? '; Secure' : ''}`;
    return get(context) === value;
  }
  const has = context => read(context).rows.some(row => row[0] === `${context.league_id}:${context.roster_id}`);
  window.dtosStrategy = {get, set, has};
  const root = document.querySelector('[data-my-team-context]');
  if (!root) return;
  const context = JSON.parse(root.dataset.myTeamContext), select = document.getElementById('my-team-strategy');
  if (select) {
    const reconcile = () => { select.value = get(context); };
    reconcile();
    addEventListener('focus', reconcile);
    addEventListener('pageshow', reconcile);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) reconcile(); });
    select.onchange = () => {
      const ok = set(context, select.value);
      document.getElementById('my-team-strategy-feedback').textContent = ok ? 'Strategy saved for this league and franchise in this signed-in browser session.' : 'Strategy could not be retained. Browser session storage is unavailable or full.';
    };
  }
  const key = 'dtos-my-team:' + context.binding;
  root.querySelector('a[href="#full-roster"]')?.addEventListener('click', () => {
    document.getElementById('my-team-roster').open = true;
  });
  try {
    const keys = Object.keys(sessionStorage).filter(k => k.startsWith('dtos-my-team:'));
    while (keys.length >= 64 && !keys.includes(key)) sessionStorage.removeItem(keys.shift());
    const saved = JSON.parse(sessionStorage.getItem(key) || '{}');
    root.querySelectorAll('details[id]').forEach(detail => {
      if (Object.hasOwn(saved, detail.id)) detail.open = saved[detail.id];
      detail.addEventListener('toggle', () => {
        const state = {}; root.querySelectorAll('details[id]').forEach(d => { state[d.id] = d.open; });
        sessionStorage.setItem(key, JSON.stringify(state));
      });
    });
  } catch (_) { /* Core controls remain available without browser storage. */ }
  if (location.hash === '#my-team-advanced') document.getElementById('my-team-advanced').open = true;
})();
