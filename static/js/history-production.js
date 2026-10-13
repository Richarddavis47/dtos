/* One source-scoped read per opened disclosure; no polling or persistence. */
(() => {
  if (window.dtosHistoricalProduction) return;
  window.dtosHistoricalProduction = true;
  const pending = new Map();
  const pagePath = window.location.pathname;
  function failure(target, message, reload = false, root = null) {
    target.textContent = message + ' ';
    const action = document.createElement('button');
    action.type = 'button';
    action.textContent = reload ? 'Reload this trade' : 'Retry supported production';
    action.addEventListener('click', () => reload ? window.location.reload() : load(root));
    target.append(action);
  }
  async function load(root) {
    if (root.dataset.loaded || root.dataset.loading) return;
    const target = root.querySelector('[data-production-content]');
    if (window.location.pathname !== pagePath) {
      failure(target, 'Trade context changed. Open production from the current trade.', true);
      return;
    }
    root.dataset.loading = 'true';
    target.textContent = 'Loading supported production…';
    target.setAttribute('aria-busy', 'true');
    const controller = new AbortController();
    const endpoint = root.dataset.productionEndpoint;
    pending.set(root, controller);
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    const current = () => root.isConnected && window.location.pathname === pagePath
      && root.dataset.productionEndpoint === endpoint && pending.get(root) === controller;
    try {
      const response = await fetch(endpoint, {signal: controller.signal, credentials: 'same-origin'});
      if (!response.ok) {
        const error = new Error(response.status === 409 ? 'Source evidence changed. Reload this trade.' : 'Production evidence could not be loaded.');
        error.reload = response.status === 409;
        throw error;
      }
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const next = doc.querySelector('[data-production-result]');
      if (!current()) {
        if (root.isConnected) failure(target, 'Trade context changed. Open production from the current trade.', true);
        return;
      }
      if (!next || next.dataset.league !== root.dataset.league || next.dataset.generation !== root.dataset.generation
          || next.dataset.trade !== root.dataset.trade) {
        const error = new Error('Evidence context changed. Reload this trade.');
        error.reload = true;
        throw error;
      }
      target.replaceChildren(...next.childNodes);
      root.dataset.loaded = 'true';
    } catch (error) {
      if (!current()) {
        if (root.isConnected) failure(target, 'Trade context changed. Open production from the current trade.', true);
        return;
      }
      failure(target, error.name === 'AbortError' ? 'The production request timed out or was interrupted.' : error.message, error.reload, root);
    } finally {
      window.clearTimeout(timeout);
      if (pending.get(root) === controller) pending.delete(root);
      delete root.dataset.loading;
      target.removeAttribute('aria-busy');
    }
  }
  document.addEventListener('toggle', event => {
    const root = event.target;
    if (root.matches('details[data-production-endpoint]') && root.open) load(root);
  }, true);
  window.addEventListener('pagehide', () => {
    for (const controller of pending.values()) controller.abort();
  });
  window.addEventListener('pageshow', () => {
    for (const root of document.querySelectorAll('details[data-production-endpoint][open]')) load(root);
  });
  for (const root of document.querySelectorAll('details[data-production-endpoint][open]')) load(root);
})();
