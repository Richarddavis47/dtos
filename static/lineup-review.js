/* Local clocks and an explicit, scoped recheck through the existing league sync. */
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
  const formatter = new Intl.DateTimeFormat(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
  });
  document.querySelectorAll('[data-lineup-local-time]').forEach(element => {
    const value = Date.parse(element.dateTime);
    if (Number.isFinite(value)) element.textContent = formatter.format(value);
  });

  function recheckControl(panel) {
    const token = document.querySelector('form[action="/sync"] input[name="csrf_token"]')?.value;
    if (!panel || !token) return;
    const button = panel.querySelector('[data-lineup-recheck]');
    const status = panel.querySelector('[data-lineup-recheck-status]');
    const scope = panel.dataset.lineupRecheckScope;
    const receiptKey = 'dtos-lineup-recheck';
    const show = text => { status.textContent = text; status.hidden = false; };
    button.hidden = false;
    try {
      const receipt = JSON.parse(sessionStorage.getItem(receiptKey));
      sessionStorage.removeItem(receiptKey);
      if (receipt?.scope === scope && receipt.url === location.href &&
          Date.parse(panel.dataset.lineupObserved) === Date.parse(receipt.observed)) {
        show(panel.dataset.lineupHasFallback === 'true' ?
          'Submitted lineup rechecked.' : 'Submitted lineup rechecked. No conditional fallback is shown.');
        status.focus();
      }
    } catch { /* Saved feedback is optional. */ }

    let attempt = 0;
    window.addEventListener('pagehide', () => {
      if (button.disabled) {
        attempt += 1;
        button.disabled = false;
        show('Recheck to confirm the current submitted lineup.');
      }
    });
    button.addEventListener('click', async () => {
      const selected = ++attempt;
      const url = location.href;
      const current = () => selected === attempt && location.href === url && panel.isConnected;
      button.disabled = true;
      show('Checking the submitted lineup with Sleeper…');
      document.querySelectorAll('[data-review-until]').forEach(review => {
        review.querySelector('[data-review-current]').hidden = true;
        review.querySelector('h3').textContent = 'Review your lineup';
        review.removeAttribute('data-review-until');
        review.dataset.lineupReview = 'rechecking';
      });
      let text = 'The lineup recheck failed. The previous lineup is still displayed. Try again when ready.';
      try {
        const response = await fetch('/sync', {
          method: 'POST', redirect: 'error',
          headers: {'Accept': 'application/json', 'X-CSRF-Token': token, 'X-DTOS-Lineup-Recheck': scope},
        });
        const result = await response.json();
        if (!current()) return;
        if (response.ok && result.status === 'updated' && result.scope === scope &&
            Number.isFinite(Date.parse(result.observed_at))) {
          try {
            sessionStorage.setItem(receiptKey, JSON.stringify({scope, url, observed: result.observed_at}));
          } catch { /* Rechecking still works without saved feedback. */ }
          location.reload();
          return;
        }
        if (result.status === 'deferred')
          text = 'The lineup recheck is waiting for capacity. Try again in a minute.';
        else if (result.status === 'scope_changed' || (response.ok && result.scope !== scope))
          text = 'The league or week changed. Open your current lineup before rechecking.';
        else if (result.status === 'not_updated')
          text = 'Sleeper did not return a newer submitted lineup. Try again when current data is available.';
      } catch { /* Keep advice withheld on transport or session failure. */ }
      if (current()) {
        show(text);
        button.disabled = false;
      }
    });
  }
  recheckControl(document.querySelector('[data-lineup-recheck-scope]'));

  check();
  document.addEventListener('visibilitychange', check);
})();
