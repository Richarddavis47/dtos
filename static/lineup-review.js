/* Time-only invalidation; no polling, fetching, analytics or lineup mutation. */
(() => {
  let timer;
  const check = () => {
    clearTimeout(timer);
    let delay = 900001;
    document.querySelectorAll('[data-review-until]').forEach(panel => {
      const until = Date.parse(panel.dataset.reviewUntil);
      // Navigation starts before server verification. Its full lifetime
      // conservatively includes response transfer, even with a slow wall clock.
      const checked = Date.parse(panel.dataset.reviewCheckedAt);
      const remaining = until - checked - performance.now();
      if (!Number.isFinite(until) || !Number.isFinite(remaining) || Date.now() >= until || remaining <= 0) {
        const current = panel.querySelector('[data-review-current]');
        const moveFocus = current.contains(document.activeElement);
        panel.dataset.lineupReview = 'expired';
        panel.querySelector('h3').textContent = 'Review your lineup';
        current.hidden = true;
        panel.querySelector('[data-review-expired]').hidden = false;
        panel.removeAttribute('data-review-until');
        if (moveFocus) panel.querySelector('a').focus({preventScroll: true});
      } else {
        delay = Math.min(delay, until - Date.now() + 1, remaining + 1);
      }
    });
    if (document.querySelector('[data-review-until]')) timer = setTimeout(check, delay);
  };
  check();
  document.addEventListener('visibilitychange', check);
})();
