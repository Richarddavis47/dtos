/* Time-only invalidation; no polling, fetching, analytics or lineup mutation. */
(() => {
  let timer;
  const check = () => {
    clearTimeout(timer);
    let delay = 900001;
    document.querySelectorAll('[data-review-until]').forEach(panel => {
      const until = Date.parse(panel.dataset.reviewUntil);
      if (!Number.isFinite(until) || Date.now() >= until) {
        panel.dataset.lineupReview = 'expired';
        panel.querySelector('h3').textContent = 'Review your lineup';
        panel.querySelector('[data-review-current]').hidden = true;
        panel.querySelector('[data-review-expired]').hidden = false;
        panel.removeAttribute('data-review-until');
      } else {
        delay = Math.min(delay, until - Date.now() + 1);
      }
    });
    if (document.querySelector('[data-review-until]')) timer = setTimeout(check, delay);
  };
  check();
  document.addEventListener('visibilitychange', check);
})();
