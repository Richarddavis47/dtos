/* Saved goal view. Legacy session intent is read-only; Trade never writes it. */
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
    if (context.franchise_goal_revision > 0 && allowed.includes(context.franchise_goal)) return context.franchise_goal;
    const value = read(context).rows.find(row => row[0] === `${context.league_id}:${context.roster_id}`)?.[1];
    return allowed.includes(value) ? value : '';
  }
  window.dtosStrategy = {get};
  const root = document.querySelector('[data-my-team-context]');
  if (!root) return;
  const context = JSON.parse(root.dataset.myTeamContext), select = document.getElementById('my-team-strategy');
  if (select) {
    let dirty = false;
    const reconcile = () => {
      if (!dirty) select.value = get(context);
      const outlook = document.getElementById('my-team-outlook');
      const choice = JSON.parse(outlook?.dataset.outlookGoals || '{}')[select.value];
      if (choice) {
        document.getElementById('my-team-outlook-goal').textContent = choice.guidance;
        const action = document.getElementById('my-team-outlook-action');
        action.textContent = choice.action; action.setAttribute('href', choice.href);
      }
    };
    reconcile();
    addEventListener('focus', reconcile);
    addEventListener('pageshow', reconcile);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) reconcile(); });
    select.onchange = () => {
      dirty = true;
      document.getElementById('my-team-strategy-feedback').textContent = 'Unsaved goal preview. Choose Save goal to change your franchise preference; Trade choices stay separate.';
      reconcile();
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
      if (detail.id !== 'my-team-roster' && Object.hasOwn(saved, detail.id)) detail.open = saved[detail.id];
      detail.addEventListener('toggle', () => {
        const state = {}; root.querySelectorAll('details[id]').forEach(d => { state[d.id] = d.open; });
        sessionStorage.setItem(key, JSON.stringify(state));
      });
    });
  } catch (_) { /* Core controls remain available without browser storage. */ }
  if (location.hash === '#my-team-advanced') document.getElementById('my-team-advanced').open = true;
  if (location.hash === '#full-roster') document.getElementById('my-team-roster').open = true;
})();
