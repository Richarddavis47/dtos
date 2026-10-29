/* Bounded, tab-local route history. Client state is never authorization. */
(() => {
  'use strict';
  const scope = document.querySelector('meta[name="dtos-navigation-scope"]')?.content;
  const back = document.getElementById('dtos-back');
  if (!scope || !back) return;
  const team = document.querySelector('meta[name="dtos-navigation-team"]')?.content || '/teams';
  const key = 'dtos-contextual-navigation:v1', maxEntries = 32, ttl = 2 * 60 * 60 * 1000;
  const byteLength = value => new TextEncoder().encode(value).byteLength;
  const uuid = () => crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  const tab = window.name.match(/\|dtos-trade-tab=([a-zA-Z0-9-]+)$/)?.[1] || uuid();
  if (!window.name.endsWith('|dtos-trade-tab=' + tab)) window.name += '|dtos-trade-tab=' + tab;
  const paths = new Set(['', 'teams', 'league', 'matchups', 'market', 'players', 'trades', 'picks', 'history', 'fois', 'front-offices', 'transactions', 'reports', 'settings', 'brain', 'valuation', 'commissioner', 'account', 'search']);
  const queryKeys = new Set(['q','position','availability','sort','direction','front_office','selected','offset','limit','week','season','year','round','from_team','from_section','from_trade','from_market','market_league','matchup','asset_id','owner_roster_id','home_offer','partner_roster_id','shop_preference','league','league_id','view','tab','format','team','scope','owner','type','player','draft_pick','date_from','date_to','status','page','per_page','from_home','since']);
  const sections = new Set(['#full-roster','#positional-depth','#draft-capital','#my-team-advanced']);
  function safeUrl(raw) {
    if (!raw || typeof raw !== 'string' || raw.length > 2400 || /[\x00-\x1f\\]/.test(raw)) return null;
    try {
      const u = new URL(raw, location.origin);
      if (u.origin !== location.origin || u.username || u.password || !['http:','https:'].includes(u.protocol)) return null;
      const decoded = decodeURIComponent(u.pathname);
      if (decoded.replace(/\/$/,'') === '/transactions/refresh') return null;
      if (/[\x00-\x1f\\]/.test(decoded) || decoded.includes('//') || !paths.has(decoded.split('/')[1] || '')) return null;
      if (decoded.startsWith('/account') && !['/account','/account/my-dtos','/account/leagues','/account/sleeper'].includes(decoded.replace(/\/$/, ''))) return null;
      const query = new URLSearchParams();
      for (const [k,v] of u.searchParams) if (queryKeys.has(k) && v.length <= 1600 && !query.has(k)) {
        if (k === 'from_market' && (!v.startsWith('/market') || v.startsWith('//'))) continue;
        query.append(k,v);
      }
      // Action/refresh/credential parameters are never replayed by Back.
      return (u.pathname.replace(/\/$/, '') || '/') + (query.size ? '?' + query : '') + (sections.has(u.hash) && /^\/teams(?:\/\d+)?\/?$/.test(u.pathname) ? u.hash : '');
    } catch (_) { return null; }
  }
  function identity(url) {
    const u = new URL(url, location.origin);
    if (u.pathname === '/teams') u.pathname = team;
    const own = team.split('/').pop();
    if (u.searchParams.get('front_office') === own) u.searchParams.delete('front_office');
    u.searchParams.sort(); return u.pathname + (u.search ? u.search : '') + u.hash;
  }
  function label(url) {
    const u = new URL(url, location.origin), first = u.pathname.split('/')[1];
    if (u.pathname === '/account/my-dtos') return 'My DTOS';
    if (u.pathname.startsWith('/trades/history/')) return 'Trade history';
    if (first === 'teams' && !['/teams',team].includes(u.pathname)) return 'Team details';
    if (u.hash === '#positional-depth') return 'Depth';
    if (u.hash === '#draft-capital') return 'Capital';
    return ({'':'Home', teams:'My Team', market:'Market', players:'Player details', trades:'Trade workspace', league:'League', matchups:'Matchups', picks:'Draft Capital', history:'History', fois:'FOIS', 'front-offices':'Franchise details', account:'Account', reports:'Weekly Report', settings:'Settings'})[first] || 'previous page';
  }
  function parent() {
    const p = location.pathname;
    const linked = document.querySelector('a.back[href]');
    const supplied = linked && safeUrl(linked.href);
    if (supplied && /^\/(market\?|teams\/|matchups\/|trades\/history\/|players\/)/.test(supplied) && identity(supplied) !== identity(safeUrl(location.href) || '/')) return supplied;
    if (p.startsWith('/players/') || p.startsWith('/picks/')) return p.startsWith('/players/') ? '/market' : '/picks';
    if (p.startsWith('/teams') && sections.has(location.hash)) return team;
    if (p.startsWith('/trades/')) return '/trades';
    if (p.startsWith('/account/')) return '/account';
    if (/^\/(fois|history|matchups|front-offices)(\/|$)/.test(p)) return '/league';
    return '/';
  }
  let ledger, entry, checking = null, restoring = false, clickBusy = false, active = true, checkGeneration = 0, checkController = null, lastRestoredFocus = null;
  const now = () => Date.now();
  const fresh = () => ({version:1,scope,tab,entries:[],cursor:null,expires:now()+ttl});
  function load() {
    try {
      const raw = sessionStorage.getItem(key);
      if (!raw || raw.length > 65536 || byteLength(raw) > 65536) return fresh();
      const x = JSON.parse(raw);
      if (x.version !== 1 || x.scope !== scope || x.tab !== tab || x.expires < now() || !Array.isArray(x.entries) || x.entries.length > maxEntries) return fresh();
      const ids = new Set(), positions = new Set();
      for (const e of x.entries) {
        if (typeof e.id !== 'string' || e.id.length > 80 || ids.has(e.id) || !Number.isSafeInteger(e.pos) || e.pos < 0 || positions.has(e.pos) || safeUrl(e.url) !== e.url) return fresh();
        ids.add(e.id);positions.add(e.pos);
      }
      if (x.entries.some((e,i)=>i && e.pos!==x.entries[i-1].pos+1)) return fresh();
      return {version:1,scope,tab,expires:x.expires,cursor:x.cursor,
        entries:x.entries.map(e=>({id:e.id,pos:e.pos,url:e.url,
          scroll:Number.isFinite(e.scroll)?Math.max(0,Math.min(1000000,e.scroll)):0,
          focusId:typeof e.focusId==='string'?e.focusId.slice(0,80):'',focusHref:safeUrl(e.focusHref)})),
        pending:x.pending && typeof x.pending.from==='string' && safeUrl(x.pending.to) && x.pending.until>=now() && x.pending.until<=now()+30000 ? {from:x.pending.from,to:safeUrl(x.pending.to),until:x.pending.until,replace:x.pending.replace===true}:null,
        left:x.left && typeof x.left.id==='string' && x.left.until>=now() && x.left.until<=now()+30000 ? {id:x.left.id,until:x.left.until}:null};
    } catch (_) { return fresh(); }
  }
  function save() {
    try {
      ledger.expires = now()+ttl;
      ledger.entries = ledger.entries.slice(-maxEntries);
      while (byteLength(JSON.stringify(ledger)) > 65536 && ledger.entries.length > 1) ledger.entries.shift();
      sessionStorage.setItem(key, JSON.stringify(ledger));
    } catch (_) {
      let notice=document.getElementById('dtos-navigation-storage');
      if (!notice) {notice=document.createElement('p');notice.id='dtos-navigation-storage';notice.setAttribute('role','status');back.closest('.dtos-page-title')?.after(notice);}
      notice.textContent="Your browser couldn't save this page's return context. Back may open a parent page. Keep active Trade work open while reviewing it.";
    }
  }
  function meta() { return history.state?.dtosNavigation; }
  function record() {
    if (!entry) return;
    const url = safeUrl(location.href); if (url) entry.url = url;
    entry.scroll = Math.max(0, Math.min(1000000, scrollY));
    const active = document.activeElement;
    entry.focusId = active?.id?.slice(0,80) || '';
    entry.focusHref = active?.closest('a[href]') ? safeUrl(active.closest('a[href]').href) : null;
    save();
  }
  function setMeta() {
    try { history.replaceState({...history.state,dtosNavigation:{scope,tab,id:entry.id,pos:entry.pos}},''); } catch (_) { /* Parent fallback is still available. */ }
  }
  function previous() {
    if (!entry || meta()?.id !== entry.id || meta()?.scope !== scope) return null;
    return [...ledger.entries].reverse().find(e => e.pos < entry.pos && identity(e.url) !== identity(entry.url));
  }
  function paint() {
    const prev = previous(), target = prev?.url || parent();
    back.hidden = identity(target) === identity(entry?.url || safeUrl(location.href) || '/');
    back.href = target; back.setAttribute('aria-label','Go back to ' + label(target));
    back.title = 'Back to ' + label(target);
  }
  function initialize() {
    ledger = load(); const url = safeUrl(location.href); if (!url) {back.hidden=true;return;}
    const m = meta();
    const old = m?.scope === scope && m.tab === tab ? ledger.entries.find(e => e.id === m.id && e.pos === m.pos) : null;
    if (old) { entry=old;entry.url=url;restoring=true; }
    else {
      const from = ledger.entries.find(e => e.id === ledger.cursor);
      const pending = ledger.pending;
      const byLink = from && pending?.from === from.id && pending.until >= now() && pending.to && identity(pending.to) === identity(url);
      const ref = safeUrl(document.referrer);
      const byRef = from && ledger.left?.id === from.id && ledger.left.until >= now() && ref && identity(ref) === identity(from.url);
      const samePage = from && identity(from.url) === identity(url);
      const linked = byLink || byRef || (samePage && performance.getEntriesByType('navigation')[0]?.type === 'reload');
      if (!linked) ledger=fresh();
      else ledger.entries=ledger.entries.filter(e=>e.pos<(pending?.replace===true?from.pos:from.pos+1));
      entry={id:uuid(),pos:linked?from.pos+(pending?.replace===true?0:1):0,url,scroll:0,focusId:'',focusHref:null};ledger.entries.push(entry);
    }
    ledger.cursor=entry.id;delete ledger.pending;delete ledger.left;setMeta();save();paint();
  }
  function restoreView() {
    if (!restoring || !entry || document.documentElement.classList.contains('dtos-nav-suspended')) return;
    const apply = () => {
      if (!active || !restoring) return;
      const focused = document.activeElement;
      if (focused && focused !== document.body && focused !== document.documentElement && focused !== lastRestoredFocus) {restoring=false;return;}
      let focus = entry.focusId ? document.getElementById(entry.focusId) : null;
      if (!focus && entry.focusHref) focus=[...document.querySelectorAll('a[href]')].find(a=>safeUrl(a.href)===entry.focusHref);
      if (focus && !focus.disabled && focus.getClientRects().length) {lastRestoredFocus=focus;focus.focus({preventScroll:true});}
      scrollTo({top:Number.isFinite(entry.scroll)?entry.scroll:0,behavior:'instant'});
    };
    requestAnimationFrame(apply);
  }
  let checkNotice;
  function suspend() {
    document.documentElement.classList.add('dtos-nav-suspended');
    document.querySelector('main')?.setAttribute('inert','');
    if (!checkNotice) {checkNotice=document.createElement('div');checkNotice.className='dtos-nav-check';checkNotice.setAttribute('role','status');document.body.append(checkNotice);}
    checkNotice.textContent='Checking your account and selected league…';checkNotice.hidden=false;
  }
  async function verify() {
    if (checking) return checking;
    const serial=checkGeneration;checkController=new AbortController();
    const controller=checkController;
    checking=(async()=>{
      await Promise.resolve();
      try {
        const r=await fetch('/api/account/navigation-context',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
        if (!active || serial!==checkGeneration) return false;
        if ([401,403].includes(r.status)) {
          active=false;
          try {sessionStorage.removeItem(key);}catch (_){}
          dispatchEvent(new Event('dtos:context-invalidated'));location.replace('/');return false;
        }
        if (!r.ok) throw new Error('Context check unavailable');
        const current=await r.json();
        if (!active || serial!==checkGeneration) return false;
        if (typeof current.scope !== 'string' || !/^[a-f0-9]{64}$/.test(current.scope)) throw new Error('Context check incomplete');
        if (current.scope !== scope) {
          active=false;
          try {sessionStorage.removeItem(key);}catch (_){}
          dispatchEvent(new Event('dtos:context-invalidated'));location.replace('/');return false;
        }
        document.documentElement.classList.remove('dtos-nav-suspended');document.querySelector('main')?.removeAttribute('inert');if(checkNotice)checkNotice.hidden=true;return true;
      } catch (_) {
        if (!active || serial!==checkGeneration) return false;
        if (checkNotice && document.documentElement.classList.contains('dtos-nav-suspended')) {
          checkNotice.textContent='Your account context could not be verified. Reload to continue safely. ';
          const reload=document.createElement('button');reload.type='button';reload.textContent='Reload page';reload.onclick=()=>location.reload();checkNotice.append(reload);
        }
        return false;
      } finally { if(serial===checkGeneration){checking=null;checkController=null;} }
    })();return checking;
  }
  function replace(url) {
    const to=safeUrl(url);if(!to)return;
    record();ledger.pending={from:entry.id,to,replace:true,until:now()+30000};save();location.replace(to);
  }
  window.dtosNavigation={verify,restoreView,replace,get checking(){return !!checking;}};
  initialize();
  if (!entry) { window.dtosNavigation=null;return; }
  back.addEventListener('click',async event=>{
    if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();if(clickBusy)return;clickBusy=true;back.setAttribute('aria-busy','true');
    const prev=previous(),target=prev?.url || parent();
    try {
      if (!(await verify())) {
        let status=document.getElementById('dtos-back-status');
        if (!status) {status=document.createElement('p');status.id='dtos-back-status';status.setAttribute('role','status');back.closest('.dtos-page-title')?.after(status);}
        status.textContent='Back could not verify your account context. Try Back again, or reload this page.';return;
      }
      document.getElementById('dtos-back-status')?.remove();
      record();dispatchEvent(new Event('dtos:navigation-leave'));
      const distance=prev && entry.pos-prev.pos;
      if (distance>0 && distance<=maxEntries && distance<history.length) history.go(-distance);
      else replace(target);
    } finally {clickBusy=false;back.removeAttribute('aria-busy');}
  });
  document.addEventListener('click',event=>{
    if(event.defaultPrevented||event.button||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    const a=event.target.closest('a[href]');if(!a||a===back||a.download||a.target&&a.target!=='_self')return;
    const to=safeUrl(a.href);if(!to)return;
    record();ledger.pending={from:entry.id,to,until:now()+30000};save();
    if(a.closest('.manager-nav') && new URL(to,location.origin).pathname==='/trades'){
      try {
        const k='dtos-trade-workspace:'+scope,saved=JSON.parse(sessionStorage.getItem(k)||'null');
        if(saved&&(!saved.tabOwner||saved.tabOwner===tab))sessionStorage.setItem(k,JSON.stringify({...saved,endedAtHome:true,resetGeneration:uuid()}));
      }catch (_){}
    }
    dispatchEvent(new Event('dtos:navigation-leave'));
  });
  document.addEventListener('submit',event=>{
    if(event.defaultPrevented)return;
    record();dispatchEvent(new Event('dtos:navigation-leave'));
  });
  addEventListener('pagehide',()=>{
    if(active){record();ledger.left={id:entry.id,until:now()+30000};save();}active=false;checkGeneration++;checkController?.abort();checking=null;checkController=null;suspend();
  });
  let lastHref = location.href;
  function traversed() {
    const changedHref = lastHref !== location.href; lastHref = location.href;
    const m=meta(),known=m?.scope===scope&&m.tab===tab&&ledger.entries.find(e=>e.id===m.id);
    if(known && !(known.id === entry?.id && changedHref)){entry=known;ledger.cursor=entry.id;restoring=true;save();paint();restoreView();return;}
    // Native hash steps count toward browser traversal, but only explicit Team
    // section shortcuts become meaningful destinations. Disclosures add none.
    const url=safeUrl(location.href);
    if(url && new URL(url,location.origin).pathname===new URL(entry.url,location.origin).pathname){
      ledger.entries=ledger.entries.filter(e=>e.pos<=entry.pos);
      entry={id:uuid(),pos:entry.pos+1,url,scroll:scrollY,focusId:'',focusHref:null};ledger.entries.push(entry);ledger.cursor=entry.id;setMeta();save();paint();
    } else initialize();
  }
  addEventListener('popstate',traversed);
  addEventListener('hashchange',()=>{if(lastHref !== location.href)traversed();});
  addEventListener('pageshow',async event=>{
    active=true;
    if(event.persisted){suspend();if(!(await verify()))return;ledger=load();traversed();}
    else restoreView();
  });
  for (const name of ['pointerdown','keydown','wheel','touchstart']) addEventListener(name,event=>{if(event.isTrusted)restoring=false;},{passive:true});
  addEventListener('load',restoreView);
})();

/* Access to the same Back link; no additional history, storage or requests. */
(() => {
  'use strict';
  const back = document.getElementById('dtos-back');
  if (!back || !window.dtosNavigation || !window.IntersectionObserver) return;
  const slot = document.createElement('span'); slot.className = 'dtos-back-slot'; slot.hidden = back.hidden;
  back.before(slot); slot.append(back);
  const dock = document.createElement('div'); dock.className = 'dtos-back-dock'; dock.hidden = true; dock.setAttribute('aria-hidden', 'true');
  const caption = document.createElement('span'); caption.className = 'dtos-back-caption'; caption.setAttribute('aria-hidden', 'true');
  dock.append(caption); document.body.append(dock);
  let frame = null, enabled = true;
  function restore() {
    dock.hidden = true; document.documentElement.classList.remove('dtos-back-docked');
    slot.style.width = ''; slot.style.height = '';
  }
  function update() {
    frame = null;
    slot.hidden = back.hidden;
    if (!enabled || back.hidden) { restore(); return; }
    const above = slot.getBoundingClientRect().bottom <= 0;
    if (!above) { restore(); return; }
    if (!document.documentElement.classList.contains('dtos-back-docked')) {
      const rect = slot.getBoundingClientRect();
      slot.style.width = rect.width + 'px'; slot.style.height = rect.height + 'px';
    }
    caption.textContent = back.title || 'Back to your previous page';
    dock.hidden = false; document.documentElement.classList.add('dtos-back-docked');
  }
  function schedule() { if (frame === null) frame = requestAnimationFrame(update); }
  const observer = new IntersectionObserver(schedule); observer.observe(slot);
  new MutationObserver(schedule).observe(back, {attributes:true, attributeFilter:['hidden','href','title','aria-label']});
  addEventListener('resize', () => { restore(); schedule(); }, {passive:true});
  addEventListener('pageshow', () => { enabled = true; schedule(); });
  addEventListener('pagehide', () => { enabled = false; if (frame !== null) cancelAnimationFrame(frame); frame = null; restore(); });
  addEventListener('dtos:context-invalidated', () => { enabled = false; restore(); });
  document.addEventListener('focusin', event => {
    const target = event.target;
    if (target === back || !target.matches?.(':focus-visible')) return;
    requestAnimationFrame(() => {
      if (dock.hidden || !enabled || document.activeElement !== target) return;
      const bounds = target.getBoundingClientRect(), edge = dock.getBoundingClientRect().bottom + 8;
      if (bounds.top < edge && bounds.bottom > 0) scrollBy({top:bounds.top - edge, behavior:'instant'});
    });
  });
  schedule();
})();
