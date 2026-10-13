/* One source-scoped read per opened disclosure; no polling or persistence. */
(() => {
  if (window.dtosHistoricalProduction) return;
  window.dtosHistoricalProduction = true;
  async function load(root) {
    if (root.dataset.loaded || root.dataset.loading) return;
    root.dataset.loading = 'true';
    const target = root.querySelector('[data-production-content]');
    target.textContent = 'Loading supported production…';
    target.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(root.dataset.productionEndpoint);
      if (!response.ok) throw new Error(response.status === 409 ? 'Source evidence changed. Reload this trade.' : 'Production evidence could not be loaded.');
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const next = doc.querySelector('[data-production-result]');
      if (!next || next.dataset.league !== root.dataset.league || next.dataset.generation !== root.dataset.generation) throw new Error('Evidence context changed. Reload this trade.');
      target.replaceChildren(...next.childNodes);
      root.dataset.loaded = 'true';
    } catch (error) {
      target.textContent = error.message + ' Close and reopen this disclosure to retry.';
    } finally {
      delete root.dataset.loading;
      target.removeAttribute('aria-busy');
    }
  }
  document.addEventListener('toggle', event => {
    const root = event.target;
    if (root.matches('details[data-production-endpoint]') && root.open) load(root);
  }, true);
})();
