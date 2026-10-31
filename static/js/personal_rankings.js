/* Account-owned ranking intent. No discovery, providers, solver or background jobs. */
(() => {
  'use strict';
  const root = document.getElementById('my-dtos');
  if (!root) return;
  const el = id => document.getElementById(id), PAGE_SIZE = 25;
  let state = null, page = 0, busy = false, ready = false, requestSequence = 0, controller = null, drag = null, pendingRemoval = null, compatibilityFragmentFocused = false;
  const openRows = new Set();
  let pendingMethodPreview = null;
  function closeMethodPreview() {
    pendingMethodPreview = null;
    if (el('personal-method-dialog').open) el('personal-method-dialog').close();
  }
  async function previewMethod() {
    if (busy || !ready || !state?.initialized) return;
    const prior = state, sequence = ++requestSequence;
    busy = true; error(''); render(); status('Comparing methods with the current Market evidence…');
    try {
      const response = await fetch('/api/my-dtos', {method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': prior.csrf_token},
        body: JSON.stringify({command: 'method_preview', expected_revision: prior.revision,
          market_generation: prior.generation, context: prior.context, valuation_method: el('personal-method-select').value})});
      const result = await response.json();
      if (sequence !== requestSequence) return;
      if (!response.ok) throw new Error(result.message || result.detail || 'Comparison could not load. Retry rankings.');
      if (result.csrf_token !== prior.csrf_token || JSON.stringify(result.account_scope) !== JSON.stringify(prior.account_scope)) throw new Error('Your session or league changed. Reload rankings.');
      const preview = result.method_preview; pendingMethodPreview = preview;
      const box = el('personal-method-comparison'); box.replaceChildren();
      box.append(node('p', `Current: ${preview.current.label} · ${preview.current.personal_value_count} personal values · ${preview.current.owned_value_count} for your saved assets.`),
        node('p', `Proposed: ${preview.proposed.label} · ${preview.proposed.personal_value_count} personal values · ${preview.proposed.owned_value_count} for your saved assets.`),
        node('p', `${preview.proposed.unpriced_count} saved assets remain unpriced. Ranking revision ${preview.ranking_revision}.`));
      const source = node('details'); source.append(node('summary', 'Market publication used'), node('p', `Source ${preview.source_generation} · ${preview.generated_at || 'Publication time not supplied'}`)); box.append(source);
      if (preview.eligibility_change_count) {
        box.append(node('h3', 'Quote changes since your last review'));
        for (const change of preview.eligibility_changes) box.append(node('p', `${change.label}: ${change.change}.`));
        if (preview.eligibility_change_count > preview.eligibility_changes.length) box.append(node('p', `${preview.eligibility_change_count} eligibility changes in total. Review affected ranking assets for the remaining unavailable prices.`));
        box.append(node('p', 'Current values are recalculated below. Previous numerical prices are not stored by this review.'));
      }
      box.append(node('h3', 'Representative personal values'));
      for (const row of preview.examples) box.append(node('p', `${row.label}: ${value(row.current_value)} → ${value(row.proposed_value)}. Neutral Market ${value(row.market_value)}.`));
      box.append(node('h3', 'Hypothetical package comparisons'));
      if (!preview.packages.length) box.append(node('p', 'No owned-versus-counterparty package is supported in this snapshot. No example was invented.'));
      for (const pack of preview.packages) box.append(node('p', `Send ${pack.sent.map(r => r.label).join(' + ')}; receive ${pack.received.map(r => r.label).join(' + ')}. Current personal totals ${value(pack.current.sent)} / ${value(pack.current.received)}; proposed ${value(pack.proposed.sent)} / ${value(pack.proposed.received)}.`));
      el('personal-method-disclosure').textContent = preview.disclosure;
      el('personal-method-confirm').textContent = preview.current.method === preview.proposed.method ? 'Confirm current evidence review' : `Use ${preview.proposed.label}`;
      el('personal-method-dialog').showModal(); el('personal-method-cancel').focus({preventScroll: true}); el('personal-method-dialog').scrollTop = 0;
      status('Comparison ready. No preferences changed.');
    } catch (exc) {
      if (sequence === requestSequence) { closeMethodPreview(); ready = false; el('personal-recovery').hidden = false; error(String(exc.message)); status('No method was changed. Retry rankings before comparing again.'); }
    } finally { if (sequence === requestSequence) { busy = false; render(); } }
  }
  const navigationScope = document.querySelector('meta[name=dtos-navigation-scope]')?.content;
  let restoredView = false;
  function restoreNavigationView() {
    if (restoredView || !navigationScope || !state || state.context?.binding !== navigationScope) return;
    restoredView = true;
    const view = history.state?.dtosPersonalView;
    if (!view || view.scope !== navigationScope) return;
    if (typeof view.q === 'string') el('personal-search').value = view.q.slice(0,200);
    if (Array.from(el('personal-position').options).some(o => o.value === view.position)) el('personal-position').value = view.position;
    if (Number.isSafeInteger(view.page) && view.page >= 0 && view.page < 1000) page = view.page;
  }
  const status = message => { el('personal-status').textContent = message; };
  function error(message) { el('personal-error').hidden = !message; el('personal-error').textContent = message || ''; }
  const value = number => typeof number === 'number' && Number.isFinite(number)
    ? number.toLocaleString(undefined, {maximumFractionDigits: 2}) : 'Unavailable';
  function node(tag, text, className) { const result = document.createElement(tag); if (text != null) result.textContent = text; if (className) result.className = className; return result; }
  const rowId = row => row.asset_id;
  const savedRankCount = () => (state?.rows || []).filter(row => row.custom_ranked === true).length;
  const savedDropPosition = target => {
    const position = Number(target?.dataset.overallRank);
    return target?.dataset.customRanked === 'true' && Number.isInteger(position)
      && position >= 1 && position <= savedRankCount() ? position : null;
  };
  const prefs = row => row.preferences || state?.preferences?.[rowId(row)] || {};
  const focusAsset = key => key ? key.slice(0, key.lastIndexOf(':')) : null;
  function rowFor(id) { return id ? [...root.querySelectorAll('.personal-row')].find(row => row.dataset.assetId === id) : null; }
  function restoreFocus(key) {
    if (!key) return;
    const row = rowFor(focusAsset(key));
    if (!row) return;
    const preferred = row.querySelector(`[data-focus-key="${CSS.escape(key)}"]`);
    const visible = control => control && !control.disabled && control.getClientRects().length;
    // At an overall boundary the old direction is now disabled. Stay on this
    // exact asset and choose an enabled direction, position, or disclosure.
    const control = [preferred, ...row.querySelectorAll('.personal-reorder button, .personal-reorder input'), row.querySelector('summary')].find(visible);
    if (!control) return;
    control.focus({preventScroll: true});
    const bounds = control.getBoundingClientRect();
    const navigation = document.querySelector('.manager-nav');
    const bottom = navigation && getComputedStyle(navigation).position === 'fixed'
      ? Math.min(innerHeight, navigation.getBoundingClientRect().top) - 12 : innerHeight - 12;
    // Native "nearest" scrolling does not account for a fixed phone nav bar.
    if (bounds.top < 12) window.scrollBy(0, bounds.top - 12);
    else if (bounds.bottom > bottom) window.scrollBy(0, bounds.bottom - bottom);
  }
  function filtered() {
    const search = el('personal-search').value.trim().toLocaleLowerCase(), position = el('personal-position').value;
    const ordered = state?.mode === 'custom' ? (state?.rows || []) : [...(state?.rows || [])].sort((a, b) => (a.market_rank ?? Infinity) - (b.market_rank ?? Infinity));
    return ordered.map((row, index) => ({row, index})).filter(({row}) =>
      (!position || String(row.position || (row.asset_type === 'pick' ? 'PICK' : '')).toUpperCase() === position)
      && (!search || [row.label, row.asset_id, row.original_franchise_name, row.year, row.season].filter(Boolean).join(' ').toLocaleLowerCase().includes(search)));
  }
  function button(text, accessible, operation, focusKey) {
    const control = node('button', text, 'btn'); control.type = 'button'; control.setAttribute('aria-label', accessible);
    if (focusKey) control.dataset.focusKey = focusKey;
    control.disabled = busy || !ready || !state?.initialized || state.mode !== 'custom'; control.addEventListener('click', operation); return control;
  }
  function removalControl(assetId) {
    return [...root.querySelectorAll('[data-remove-asset]')].find(control => control.dataset.removeAsset === assetId);
  }
  function restoreRecoveryFocus(assetId) {
    const control = removalControl(assetId) || el('personal-compatibility-summary');
    if (!el('personal-compatibility').hidden && control && !control.disabled) control.focus({preventScroll: true});
    else el('personal-status').focus({preventScroll: true});
  }
  function startRemoval(issue) {
    if (busy || !ready || !state?.initialized || !issue.can_remove) return;
    pendingRemoval = issue.asset_id;
    el('personal-remove-description').textContent = `${issue.label || issue.asset_id}: ${issue.reason}`;
    el('personal-remove-confirm').setAttribute('aria-label', `Remove ${issue.label || issue.asset_id} from Custom ordering`);
    const dialog = el('personal-remove-dialog');
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    el('personal-remove-cancel').focus();
  }
  function renderCompatibility() {
    const issues = state?.compatibility_issues || [], container = el('personal-compatibility');
    container.hidden = !issues.length;
    el('personal-compatibility-summary').textContent = `Review ${issues.length} ${issues.length === 1 ? 'asset' : 'assets'} needing attention${issues.length ? ': ' + (issues[0].label || issues[0].asset_id) + (issues.length > 1 ? ' and others' : '') : ''}`;
    el('personal-compatibility-retry').disabled = busy || !ready;
    el('personal-compatibility-counts').textContent = `${state.saved_asset_count ?? (state.rows || []).filter(row => row.custom_ranked).length} assets in your saved order · ${state.eligible_asset_count ?? (state.rows || []).filter(row => row.identity_available !== false).length} currently eligible Market assets. These counts can differ; new eligible assets are not added to your saved order automatically.`;
    const list = el('personal-compatibility-issues'); list.replaceChildren();
    for (const issue of issues) {
      const item = node('li', null, 'personal-compatibility-issue');
      item.append(node('strong', issue.label || issue.asset_id), node('p', issue.reason));
      const identity = node('details', null, 'personal-asset-identity'); identity.append(node('summary', 'Exact asset identity'), node('p', issue.asset_id)); item.append(identity);
      item.append(node('p', issue.retryable
        ? 'Its evidence may return. Retry to check the latest prepared Market list; no saved rankings change.'
        : 'Retry checks current evidence. It cannot resolve an identity conflict or restore a removed asset by itself.', 'muted'));
      if (issue.can_remove) {
        const control = node('button', 'Review removal from Custom ordering', 'btn'); control.type = 'button';
        control.setAttribute('aria-label', `Review removing ${issue.label || issue.asset_id} from Custom ordering`);
        control.dataset.removeAsset = issue.asset_id; control.disabled = busy || !ready || !state.initialized;
        control.addEventListener('click', () => startRemoval(issue)); item.append(control);
      }
      list.append(item);
    }
    if (issues.length && ready && location.hash === '#personal-compatibility' && !compatibilityFragmentFocused) {
      compatibilityFragmentFocused = true; container.open = true;
      requestAnimationFrame(() => {
        const summary = el('personal-compatibility-summary'); summary.focus({preventScroll: true});
        summary.scrollIntoView({block: 'start'});
      });
    }
  }
  function render(focusKey, scrollTop, rowTop) {
    if (!state) return;
    const initialized = Boolean(state.initialized), custom = state.mode === 'custom', rankedCount = savedRankCount();
    el('personal-active-method').textContent = `${state.method_label || 'Absolute Slot'} · active Custom pricing method`;
    el('personal-method-preview').disabled = busy || !ready || !initialized;
    el('personal-method-select').disabled = busy || !ready || !initialized;
    const review = state.method_review;
    el('personal-publication-review').hidden = !review?.publication_changed;
    el('personal-publication-review').textContent = review?.publication_changed ? `${review.message} Since the last review: ${review.added_count} newly priced; ${review.removed_count} no longer priced. Use Preview method to review the current evidence.` : '';
    el('personal-neutral').setAttribute('aria-pressed', String(!custom));
    el('personal-custom').setAttribute('aria-pressed', String(custom));
    el('personal-neutral').disabled = busy || !ready; el('personal-custom').disabled = busy || !ready;
    el('personal-initialize').hidden = initialized;
    el('personal-initialize').disabled = busy || !ready || !state.rows?.length;
    el('personal-restart').hidden = !initialized;
    el('personal-restart').disabled = busy || !ready || !initialized || !state.rows?.length;
    el('personal-reload').disabled = busy;
    const warnings = state.limitations || [];
    el('personal-warnings').hidden = !warnings.length;
    el('personal-warnings').classList.toggle('is-neutral', !custom);
    el('personal-warnings').textContent = !initialized
      ? (state.rows?.length ? 'Create rankings to personalize. Neutral DTOS remains available; review the Market evidence below before setting up Custom.'
        : 'No supported Market ranking assets are ready for Custom setup. Check Market or retry rankings; saved work has not been changed.')
      : state.personal_available ? 'Custom values are ready with qualifications. Review the details before acting.'
      : state.personal_partial_available
        ? `${state.personal_value_count} saved assets have verified personal values. Other Custom values need more Market evidence; Neutral DTOS remains available. Your saved order is preserved.`
        : 'Custom Trade values need more evidence. Neutral DTOS remains available, and your saved ranking work is preserved. Review the affected assets below.';
    el('personal-warning-details').hidden = !warnings.length;
    el('personal-warning-list').replaceChildren(...warnings.map(text => node('li', text)));
    renderCompatibility();
    const scope = state.account_scope || state.context || {};
    el('personal-scope').textContent = `League ${scope.league_id || 'unavailable'} · Franchise ${scope.roster_id || 'unavailable'} · ${state.eligible_asset_count ?? state.rows?.length ?? 0} eligible ranked assets${state.initialized ? ' · ' + (state.saved_asset_count ?? (state.rows || []).filter(row => row.custom_ranked).length) + ' saved ranking assets' : ''} · Revision ${state.revision || 0}`;
    el('personal-mode-description').textContent = custom
      ? (state.personal_available ? 'Your personal values guide Custom decisions. Neutral Market fairness stays visible.'
        : state.personal_partial_available ? `${state.personal_value_count} saved assets have verified personal values. Custom calculations can use those assets; other values need the missing Market evidence. Your saved order is unchanged.`
        : 'Your saved Custom order is shown. Custom Trade values are paused until the listed assets are reviewed; Neutral Trade remains available.')
      : initialized ? 'Neutral Market values are active. Your custom order and preferences are preserved.'
      : 'Neutral DTOS is ready. Create Custom Rankings to personalize your trade decisions.';
    const method = state.method_explanation || (typeof state.method === 'object' ? state.method?.description : null);
    if (method) el('personal-method').textContent = method;
    const rows = filtered(); const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE)); page = Math.max(0, Math.min(page, pages - 1));
    for (const row of root.querySelectorAll('.personal-row')) {
      if (row.querySelector('details')?.open) openRows.add(row.dataset.assetId); else openRows.delete(row.dataset.assetId);
    }
    const list = el('personal-list'); list.replaceChildren();
    const identities = new Set((state.rows || []).map(rowId));
    for (const id of openRows) if (!identities.has(id)) openRows.delete(id);
    for (const {row, index} of rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)) {
      const id = rowId(row), label = row.label || id, rank = index + 1, editable = initialized && custom && row.custom_ranked !== false;
      const item = node('li', null, 'personal-row'); item.dataset.assetId = id; item.dataset.overallRank = String(rank); item.dataset.customRanked = String(row.custom_ranked === true); item.value = rank;
      const header = node('div', null, 'personal-row-heading');
      let details;
      const handle = button('↕', `Reorder or drag ${label} to another overall position`, () => { details.open = !details.open; }, `${id}:drag`);
      handle.disabled ||= !editable; handle.classList.add('personal-drag'); handle.draggable = !handle.disabled; handle.dataset.dragHandle = id; header.append(handle);
      const identity = node('div', null, 'personal-identity'); identity.append(node('strong', `${custom && row.custom_ranked === false ? 'Unranked' : rank + '.'} ${label}`), node('span', `${row.position || 'PICK'} · ${row.owned ? 'Your asset' : 'Not on your franchise'}`, 'muted')); header.append(identity); item.append(header);
      const values = node('p', null, 'personal-values'); values.append(node('span', `Market ${value(row.market_value)}`), node('span', initialized ? (row.personal_value_available || state.personal_available ? `Personal ${value(row.personal_value)}` : row.personal_value_reason ? 'Personal value depends on missing prices' : 'Personal value needs evidence') : 'Create rankings to personalize')); identity.append(values);
      const saved = ['target', 'avoid', 'protect'].filter(flag => prefs(row)[flag]);
      if (row.tier_start || state.tiers?.includes(id)) saved.push('Tier start');
      if (saved.length) identity.append(node('span', saved.map(flag => flag[0].toUpperCase() + flag.slice(1)).join(' · '), 'personal-saved-intent'));
      if (initialized && row.custom_ranked === false) item.append(node('p', 'Not in your saved Custom order: this asset has no personal value. Restart Rankings is a separate, optional full-baseline reset that requires confirmation.', 'personal-qualification'));
      if (row.limitation || row.unavailable_reason) item.append(node('p', row.limitation || row.unavailable_reason, 'personal-qualification'));
      details = node('details', null, 'personal-row-details'); details.open = openRows.has(id);
      const summary = node('summary', 'Edit'); summary.setAttribute('aria-label', `Edit and reorder ${label}`); summary.dataset.focusKey = `${id}:details`; details.append(summary);
      if (row.personal_value_reason) details.append(node('p', row.personal_value_reason, 'personal-qualification'));
      details.addEventListener('toggle', () => { if (!details.isConnected) return; if (details.open) openRows.add(id); else openRows.delete(id); });
      const editing = node('div', null, 'personal-editing');
      if (row.market_rank != null) editing.append(node('p', `Current Market overall #${row.market_rank}${row.personal_rank != null ? ` · Your overall #${row.personal_rank}` : ''}`, 'muted'));
      const controls = node('div', null, 'personal-reorder');
      const move = (destination, key = `${id}:position`) => {
        if (!editable || !Number.isInteger(destination) || destination < 1 || destination > rankedCount) { error('Enter an available saved ranking position.'); return; }
        command('reorder', {asset_id: id, to_position: destination}, key);
      };
      const up = button('Move Up', `Move ${label} up one overall position`, () => move(rank - 1, `${id}:up`), `${id}:up`); up.disabled ||= !editable || rank <= 1;
      const down = button('Move Down', `Move ${label} down one overall position`, () => move(rank + 1, `${id}:down`), `${id}:down`); down.disabled ||= !editable || rank >= rankedCount;
      controls.append(up, down);
      const moveLabel = node('label', 'Overall position'); moveLabel.className = 'personal-move-label';
      const input = document.createElement('input'); input.type = 'number'; input.min = '1'; input.max = String(rankedCount); input.value = String(rank); input.inputMode = 'numeric'; input.dataset.focusKey = `${id}:position`; input.setAttribute('aria-label', `Overall position for ${label}`); input.disabled = busy || !ready || !editable; moveLabel.append(input); controls.append(moveLabel);
      const moveButton = button('Move', `Move ${label} to entered overall position`, () => { const destination = Number(input.value); if (!Number.isInteger(destination) || destination < 1 || destination > rankedCount) { error('Enter an available saved ranking position.'); input.focus(); return; } move(destination); }, `${id}:move`); moveButton.disabled ||= !editable; controls.append(moveButton); editing.append(controls);
      const flags = node('div', null, 'personal-flags');
      for (const [flag, caption] of [['target', 'Target acquisition'], ['avoid', 'Prefer to avoid acquiring'], ['protect', 'Protect outgoing']]) {
        const wrap = node('label', null, 'personal-flag'); const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = Boolean(prefs(row)[flag]); checkbox.dataset.focusKey = `${id}:${flag}`;
        checkbox.setAttribute('aria-label', `${caption}: ${label}`); checkbox.disabled = busy || !ready || !initialized || row.custom_ranked === false || (flag === 'protect' && !row.owned && !checkbox.checked);
        checkbox.addEventListener('change', () => command('preferences', {asset_id: id, preferences: {...prefs(row), [flag]: checkbox.checked}}, `${id}:${flag}`)); wrap.append(checkbox, document.createTextNode(caption)); flags.append(wrap);
      }
      const tierLabel = node('label', null, 'personal-flag'); const tier = document.createElement('input'); tier.type = 'checkbox'; tier.checked = Boolean(row.tier_start || state.tiers?.includes(id)); tier.dataset.focusKey = `${id}:tier`; tier.disabled = busy || !ready || !editable; tier.setAttribute('aria-label', `Start personal tier at ${label}`); tier.addEventListener('change', () => command('tiers', {asset_id: id, tier_start: tier.checked}, `${id}:tier`)); tierLabel.append(tier, document.createTextNode('Start personal tier')); flags.append(tierLabel); editing.append(flags);
      details.append(editing); item.append(details);
      if (prefs(row).protect && !row.owned) item.append(node('p', row.owner_roster_id == null
        ? 'Your Protect choice is saved, but current ownership is not confirmed. DTOS cannot apply it to generated offers until ownership is supported.'
        : 'Saved protection is inactive because this exact asset is not currently owned by your franchise.', 'personal-qualification'));
      list.append(item);
    }
    if (!rows.length) list.append(node('li', state.rows?.length ? 'No assets match these filters. Clear the search or position filter.' : 'Prepared compatible Market rankings are unavailable. Neutral browsing remains available; reload after Market is ready.', 'personal-empty'));
    el('personal-results-count').textContent = `${rows.length} matches / ${state.rows?.length || 0} assets · Ranks are overall`;
    for (const suffix of ['', '-bottom']) {
      el('personal-page' + suffix).textContent = `Page ${page + 1} of ${pages}`;
      el('personal-previous' + suffix).disabled = busy || !ready || page === 0; el('personal-next' + suffix).disabled = busy || !ready || page + 1 >= pages;
    }
    if (scrollTop != null) window.scrollTo({top: scrollTop});
    const anchor = rowFor(focusAsset(focusKey));
    if (rowTop != null && anchor) window.scrollBy(0, anchor.getBoundingClientRect().top - rowTop);
    restoreFocus(focusKey);
  }
  async function read() {
    if (busy) return;
    closeMethodPreview();
    const sequence = ++requestSequence; controller?.abort(); controller = new AbortController(); ready = false; render(); root.setAttribute('aria-busy', 'true'); status('Checking prepared Market rankings…'); error('');
    try {
      const response = await fetch('/api/my-dtos', {credentials: 'same-origin', cache: 'no-store', signal: controller.signal}); const result = await response.json();
      if (sequence !== requestSequence) return;
      if (!response.ok) throw new Error(result.message || result.detail || 'My DTOS is unavailable. Sign in or reload and try again.');
      if ((root.dataset.csrfToken && result.csrf_token !== root.dataset.csrfToken) || root.dataset.leagueId && (String(result.account_scope?.league_id) !== root.dataset.leagueId || String(result.account_scope?.roster_id) !== root.dataset.rosterId)) throw new Error('Your selected league or franchise changed. Reload this page before using rankings.');
      const retriedWithFocus = document.activeElement === el('personal-retry') || document.activeElement === el('personal-compatibility-retry');
      state = result; ready = true; restoreNavigationView(); el('personal-recovery').hidden = true; render(); window.dtosNavigation?.restoreView(); status(result.initialized ? 'Rankings loaded. Review any evidence limits below.' : 'Market rankings loaded. Neutral DTOS is active.');
      if (retriedWithFocus) {
        if (result.compatibility_issues?.length) { el('personal-compatibility').open = true; el('personal-compatibility-summary').focus({preventScroll: true}); }
        else el(result.initialized ? 'personal-custom' : 'personal-initialize').focus({preventScroll: true});
      }
    } catch (exc) { if (sequence === requestSequence && exc.name !== 'AbortError') { error(String(exc.message)); el('personal-recovery').hidden = false; render(); status(state ? 'Previously loaded rankings are shown for reference. Retry to check current evidence before editing.' : 'Custom Rankings could not load. Check Market or retry; Neutral Trade remains available.'); } }
    finally { if (sequence === requestSequence) root.setAttribute('aria-busy', 'false'); }
  }
  async function command(name, values = {}, focusKey) {
    if (busy || !ready || !state) return;
    closeMethodPreview();
    const prior = state, scrollTop = window.scrollY, rowTop = rowFor(focusAsset(focusKey))?.getBoundingClientRect().top, activeId = document.activeElement?.id, sequence = ++requestSequence;
    busy = true; error(''); render(focusKey, scrollTop, rowTop); status('Saving your preference…');
    try {
      const response = await fetch('/api/my-dtos', {method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': prior.csrf_token}, body: JSON.stringify({command: name, expected_revision: prior.revision || 0, market_generation: prior.generation, context: prior.context, ...values})});
      const result = await response.json(); if (sequence !== requestSequence) return;
      if (!response.ok) throw new Error(result.message || result.detail || 'This change could not be saved. Reload before trying again.');
      if (prior.account_scope && result.account_scope && (prior.account_scope.league_id !== result.account_scope.league_id || prior.account_scope.roster_id !== result.account_scope.roster_id)) throw new Error('Your account or league changed. Reload before continuing.');
      state = result;
      if (focusKey) { const id = focusKey.slice(0, focusKey.lastIndexOf(':')); const index = filtered().findIndex(item => rowId(item.row) === id); if (index >= 0) page = Math.floor(index / PAGE_SIZE); }
      const moved = name === 'reorder' ? result.rows?.find(row => row.asset_id === values.asset_id) : null;
      status(name === 'remove_asset' ? `Saved. The reviewed asset was removed only from Custom ordering. Your other ranking work and saved choices are preserved. Revision ${result.revision}.` : moved ? `Saved. ${moved.label || moved.asset_id} moved to overall position ${moved.personal_rank || values.to_position} of ${savedRankCount()}. Revision ${result.revision}.` : `Saved. Revision ${result.revision}.`);
    } catch (exc) { if (sequence === requestSequence) { state = prior; ready = false; el('personal-recovery').hidden = false; error(String(exc.message)); status('The requested change was not applied to this view. Retry rankings to check saved state before editing again.'); } }
    finally {
      if (sequence === requestSequence) {
        busy = false; render(focusKey, scrollTop, rowTop);
        if (name === 'valuation_method') el('personal-method-preview').focus({preventScroll: true});
        else if (name === 'remove_asset') restoreRecoveryFocus(values.asset_id);
        else if (!focusKey) {
          const control = el(activeId);
          if (control && !control.disabled && control.getClientRects().length) control.focus({preventScroll: true});
          else if (name === 'initialize') el('personal-custom').focus({preventScroll: true});
        }
      }
    }
  }
  function startRestart() {
    el('personal-reset-flags').checked = false;
    const dialog = el('personal-restart-dialog'); if (typeof dialog.showModal === 'function') dialog.showModal(); else { dialog.setAttribute('open', ''); el('personal-restart-cancel').focus(); }
  }
  el('personal-neutral').onclick = () => { if (!state?.initialized) { status('Neutral DTOS is active. No saved rankings were created.'); return; } command('mode', {mode: 'neutral'}, ''); };
  el('personal-custom').onclick = () => state?.initialized ? command('mode', {mode: 'custom'}, '') : command('initialize', {}, '');
  el('personal-method-preview').onclick = previewMethod;
  el('personal-method-select').onchange = closeMethodPreview;
  el('personal-method-cancel').onclick = () => { closeMethodPreview(); el('personal-method-preview').focus(); };
  el('personal-method-dialog').addEventListener('cancel', () => { pendingMethodPreview = null; requestAnimationFrame(() => el('personal-method-preview').focus()); });
  el('personal-method-confirm').onclick = () => {
    const preview = pendingMethodPreview;
    if (preview) command('valuation_method', {valuation_method: preview.proposed.method, preview_token: preview.preview_token, confirmation: 'APPLY VALUATION METHOD'});
  };
  el('personal-initialize').onclick = () => command('initialize');
  el('personal-reload').onclick = read;
  el('personal-retry').onclick = read;
  el('personal-compatibility-retry').onclick = read;
  el('personal-remove-cancel').onclick = () => { const id = pendingRemoval; pendingRemoval = null; el('personal-remove-dialog').close(); restoreRecoveryFocus(id); };
  el('personal-remove-dialog').addEventListener('cancel', () => { const id = pendingRemoval; pendingRemoval = null; requestAnimationFrame(() => restoreRecoveryFocus(id)); });
  el('personal-remove-confirm').onclick = () => {
    const id = pendingRemoval; pendingRemoval = null; el('personal-remove-dialog').close();
    if (id) command('remove_asset', {asset_id: id, confirmation: 'REMOVE FROM CUSTOM ORDER'});
  };
  el('personal-restart').onclick = startRestart;
  el('personal-restart-cancel').onclick = () => { el('personal-restart-dialog').close(); el('personal-restart').focus(); };
  el('personal-restart-confirm').onclick = () => { const reset = el('personal-reset-flags').checked; el('personal-restart-dialog').close(); command('restart', {confirmation: 'RESTART RANKINGS', reset_preferences: reset}); };
  for (const id of ['personal-search', 'personal-position']) el(id).addEventListener(id === 'personal-search' ? 'input' : 'change', () => { page = 0; render(); });
  for (const suffix of ['', '-bottom']) for (const [direction, delta] of [['previous', -1], ['next', 1]]) {
    el('personal-' + direction + suffix).onclick = () => {
      if (!ready || !state || busy) return;
      page += delta; render(); el('personal-page').scrollIntoView({block: 'nearest'});
      const clicked = el('personal-' + direction), fallback = el('personal-' + (direction === 'next' ? 'previous' : 'next'));
      (clicked.disabled ? fallback : clicked).focus({preventScroll: true});
    };
  }
  root.addEventListener('dragstart', event => { const handle = event.target.closest('[data-drag-handle]'); if (!handle || handle.disabled || busy || !state?.initialized || state.mode !== 'custom') { event.preventDefault(); return; } drag = {id: handle.dataset.dragHandle}; event.dataTransfer.setData('text/plain', drag.id); event.dataTransfer.effectAllowed = 'move'; });
  root.addEventListener('dragover', event => { const target = event.target.closest('[data-overall-rank]'); if (!drag || !savedDropPosition(target)) return; event.preventDefault(); root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); target.classList.add('personal-drop-target'); });
  root.addEventListener('drop', event => { const target = event.target.closest('[data-overall-rank]'); if (!drag) return; const id = drag.id, position = savedDropPosition(target); drag = null; root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); if (!position) return; event.preventDefault(); command('reorder', {asset_id: id, to_position: position}, `${id}:drag`); });
  root.addEventListener('dragend', () => { drag = null; root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); });
  root.addEventListener('pointerdown', event => { if (event.pointerType === 'mouse') return; const handle = event.target.closest('[data-drag-handle]'); if (!handle || handle.disabled) return; event.preventDefault(); drag = {id: handle.dataset.dragHandle, pointer: event.pointerId, handle, x: event.clientX, y: event.clientY}; handle.setPointerCapture(event.pointerId); });
  root.addEventListener('pointermove', event => { if (!drag || drag.pointer !== event.pointerId) return; if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 6) return; drag.moved = true; const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-overall-rank]'); root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); drag.destination = savedDropPosition(target); if (drag.destination) target.classList.add('personal-drop-target'); });
  root.addEventListener('pointerup', event => { if (!drag || drag.pointer !== event.pointerId) return; const {id, destination, handle, moved} = drag; drag = null; if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId); root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); if (destination && moved) command('reorder', {asset_id: id, to_position: destination}, `${id}:drag`); });
  // Native HTML dragging cancels its initiating pointer. Only cancel the
  // separately captured touch gesture here; native dragend owns mouse cleanup.
  root.addEventListener('pointercancel', event => { if (!drag || drag.pointer !== event.pointerId) return; drag = null; root.querySelectorAll('.personal-drop-target').forEach(row => row.classList.remove('personal-drop-target')); });
  addEventListener('hashchange', () => { compatibilityFragmentFocused = false; if (state) renderCompatibility(); });
  addEventListener('pagehide', () => {
    closeMethodPreview();
    if (navigationScope && state?.context?.binding === navigationScope) try {
      history.replaceState({...history.state,dtosPersonalView:{scope:navigationScope,q:el('personal-search').value.slice(0,200),position:el('personal-position').value,page}},'');
    } catch (_) { /* No preference state is written by navigation. */ }
    requestSequence++; controller?.abort(); drag = null;
  });
  addEventListener('pageshow', async event => { if (event.persisted) { if (window.dtosNavigation && !(await window.dtosNavigation.verify())) return; busy = false; read(); } });
  read();
})();
