/* Bounded observation only. These checks never initiate Market preparation. */
(() => {
  'use strict';
  const root = document.querySelector('#market-preparation');
  if (!root) return;
  const scope = document.querySelector('meta[name="dtos-navigation-scope"]')?.content;
  const title = document.querySelector('#market-preparation-title');
  const message = document.querySelector('#market-preparation-message');
  const stage = document.querySelector('#market-preparation-stage');
  const recovery = document.querySelector('#market-preparation-recovery');
  const retry = document.querySelector('#market-preparation-retry');
  const target = location.pathname + location.search;
  let active = true, timer = null, controller = null, serial = 0, checks = 0, failures = 0;
  const deadline = Date.now() + 60000;
  function cancel() { serial++; clearTimeout(timer); controller?.abort(); controller = null; }
  function pause(text) { cancel(); recovery.textContent = text; }
  function expired() { return checks >= 12 || Date.now() >= deadline; }
  async function check() {
    if (!active || document.hidden || controller || !scope) return;
    if (expired()) { pause('Preparation has not been confirmed yet. Automatic checks have paused; use Try Market again to check or retry preparation. You can keep using Home and My Team.'); return; }
    checks++;
    const revision = ++serial;
    controller = new AbortController();
    const request = controller;
    const timeout = setTimeout(() => request.abort(), 8000);
    try {
      const response = await fetch('/api/account/market-preparation', {
        credentials: 'same-origin', cache: 'no-store', signal: request.signal,
        headers: {'Accept': 'application/json'}
      });
      if (!active || revision !== serial || document.hidden) return;
      if ([401, 403].includes(response.status) || response.redirected) {
        pause('Sign in again to check this league’s Market. Your saved rankings have not been changed.');
        retry.textContent = 'Sign in'; retry.href = '/account/sign-in'; return;
      }
      if (!response.ok) throw new Error('Status check failed');
      const status = await response.json();
      if (!active || revision !== serial || document.hidden) return;
      if (status.scope !== scope) {
        pause('Your account or selected league changed. Open Market again for the current league.');
        retry.textContent = 'Open current Market'; retry.href = '/market'; return;
      }
      if (!['waiting', 'preparing', 'failed', 'incompatible', 'empty', 'ready', 'stale'].includes(status.state)
          || typeof status.title !== 'string' || typeof status.message !== 'string') throw new Error('Incomplete status');
      failures = 0;
      title.textContent = status.title; message.textContent = status.message;
      stage.textContent = status.stage;
      if (['ready', 'stale'].includes(status.state)) {
        stage.textContent = 'Opening the compatible Market…';
        if (await window.dtosNavigation?.verify()) {
          if (active && revision === serial && !document.hidden) {
            cancel(); window.dtosNavigation.replace(target); return;
          }
        }
        pause('Market is ready. Use Try Market again to open it after your account context can be checked.'); return;
      }
      if (!status.can_check) {
        pause('Automatic checks have paused. Use Try Market again to request preparation, or continue to Home or My Team.'); return;
      }
    } catch (_) {
      if (!active || revision !== serial || document.hidden) return;
      failures++;
      if (failures >= 3) {
        pause('The readiness check could not connect. Use Try Market again when your connection is available; this does not mean your saved rankings were lost.'); return;
      }
      stage.textContent = 'The readiness check could not connect. Checking again shortly.';
    } finally {
      clearTimeout(timeout);
      if (revision === serial) controller = null;
    }
    if (active && !document.hidden && revision === serial) timer = setTimeout(check, 5000);
  }
  addEventListener('dtos:context-invalidated', () => { active = false; cancel(); });
  addEventListener('pagehide', () => { active = false; cancel(); });
  addEventListener('pageshow', () => { active = true; check(); });
  document.addEventListener('visibilitychange', () => { cancel(); if (!document.hidden) check(); });
  if (!scope) recovery.textContent = 'Use Try Market again to check manually. No background readiness checks are running.';
  else check();
})();
