/* Selected-week presentation only: no global league/week mutation. */
(() => {
  if (window.dtosPlayerWeekNavigation) return;
  window.dtosPlayerWeekNavigation = true;
  let pending;
  async function showWeek(root, query) {
    if (pending) pending.abort();
    pending = new AbortController();
    const controller = pending;
    const status = root.querySelector('.projection-navigation-status');
    status.textContent = 'Loading week…';
    root.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(`${root.dataset.weekEndpoint}?${query}`, {signal: controller.signal});
      if (!response.ok) throw new Error('Week unavailable');
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const next = doc.getElementById('player-weekly-projections');
      if (!next || controller !== pending) return;
      root.replaceWith(next);
      next.querySelector('select').focus();
      history.replaceState(null, '', `${location.pathname}?${query}`);
    } catch (error) {
      if (error.name !== 'AbortError') status.textContent = 'Unable to load this week. Please try again.';
    } finally {
      root.removeAttribute('aria-busy');
    }
  }
  document.addEventListener('submit', event => {
    const root = event.target.closest('#player-weekly-projections');
    if (!root) return;
    event.preventDefault();
    showWeek(root, new URLSearchParams(new FormData(event.target)));
  });
  document.addEventListener('click', event => {
    const link = event.target.closest('#player-weekly-projections nav a');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    showWeek(link.closest('#player-weekly-projections'), new URL(link.href).searchParams);
  });
})();
