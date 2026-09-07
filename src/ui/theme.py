"""Canonical, framework-free DTOS presentation tokens and layout primitives.

No intelligence is derived here. Legacy variable names remain aliases so existing
specialized renderers share the same palette during the component migration.
"""

DESIGN_SYSTEM_CSS = """
:root{
 --background:#050b10;--surface:#09131c;--surface-elevated:#101e29;
 --surface-interactive:#142634;--border:#20313d;--border-active:#79d84a;
 --text-primary:#f2f6f8;--text-secondary:#b6c2cb;--text-muted:#97a8b5;
 --accent-primary:#80df42;--accent-secondary:#4baafa;--positive:#8ada62;
 --warning:#e8bd63;--negative:#fa818a;--info:#77bafa;--value-color:#62b6fc;
 --focus:#bceaff;--space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;
 --space-5:24px;--space-6:32px;--space-7:48px;--control-height:44px;
 --type-meta:12px;--type-body:14px;--type-title:28px;--content-width:1240px;
 --radius-sm:8px;--radius-md:12px;--radius-lg:16px;--radius-xl:20px;
 --shadow-card:0 5px 18px rgba(0,0,0,.15);
 --bg:var(--background);--surface-0:var(--background);--surface-1:var(--surface);
 --surface-2:var(--surface-elevated);--surface-3:var(--surface-interactive);
 --panel:var(--surface-elevated);--line:var(--border);--line-strong:#415966;
 --text:var(--text-primary);--muted:var(--text-muted);--accent:var(--accent-primary);
 --accent-strong:#66c839;--blue:var(--value-color);--gold:var(--warning);
 --purple:#c597ed;--danger:var(--negative)
}
body{background:var(--background);font-size:var(--type-body);line-height:1.5}
.wrap{max-width:var(--content-width);padding:18px 24px 32px;min-width:0}
.wrap>*,.grid>*,.ux-command-grid>*,.ds-page-header>*{min-width:0}
h1,h2,h3{color:var(--text-primary);text-wrap:balance;line-height:1.2}
button,input,select,textarea{font:inherit}
button,select,input:not([type=hidden]),.btn{min-height:var(--control-height)}
button,.btn{cursor:pointer}
button:disabled{cursor:wait;opacity:.65}
button,.btn,.ds-action{border:1px solid var(--border);border-radius:var(--radius-sm)}
button:not(.btn):not(.primary){background:var(--surface-elevated);color:var(--text)}
input,select,textarea{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px 12px;max-width:100%}
a,button,summary{-webkit-tap-highlight-color:transparent}
summary{min-height:44px;align-content:center;cursor:pointer}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,textarea:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
a:active,button:active{filter:brightness(.9)}
.card{background:var(--surface);border:1px solid var(--border);box-shadow:none;border-radius:var(--radius-lg);padding:18px}
a.card:hover,a.team-link:hover,.ux-action:hover{border-color:var(--line-strong);background:var(--surface-elevated)}
.top{margin:0;gap:16px;min-height:56px;flex-wrap:nowrap}
.brand-mark{display:block;min-height:44px;line-height:44px;font-size:24px;letter-spacing:.12em;font-weight:800;color:var(--text);text-decoration:none}
.brand-mark:first-letter{color:var(--accent)}
.brand p{font-size:12px;margin:2px 0;color:var(--text-secondary)}
.top .btn{background:transparent;color:var(--text-secondary);border:1px solid var(--border);font-size:12px}
.account-context{position:relative;border-bottom:1px solid var(--border);padding:10px 0;margin-bottom:8px}
.account-context summary{cursor:pointer;display:flex;align-items:center;gap:10px;min-height:44px;list-style:none}
.account-context summary::-webkit-details-marker{display:none}
.account-context summary:after{content:"⌄";margin-left:auto;color:var(--accent)}
.account-context summary b{font-size:13px}
.account-context summary span{font-size:12px;color:var(--text-muted)}
.account-context .ds-actions{max-height:280px;overflow-y:auto;justify-content:flex-start;padding:12px 0}
.account-context button[aria-current=true]{border-color:var(--accent);color:var(--accent)}
.manager-nav{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));margin:0 0 8px;gap:4px;border-bottom:1px solid var(--border)}
.manager-nav a{display:flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:8px;border-bottom:2px solid transparent;font-weight:650;color:var(--text-secondary)}
.manager-nav a[aria-current=page]{border-color:var(--accent);color:var(--accent);background:linear-gradient(0deg,rgba(128,223,66,.06),transparent)}
.nav-icon{width:22px;height:22px;flex-shrink:0}
.secondary-nav{margin-bottom:16px;font-size:12px;color:var(--muted)}
.secondary-nav summary{cursor:pointer;min-height:44px;display:flex;align-items:center}
.secondary-nav div{display:flex;gap:8px;flex-wrap:wrap}
.secondary-nav a{display:inline-flex;align-items:center;min-height:44px;padding:10px;border:1px solid var(--border);border-radius:var(--radius-sm)}
.ds-page-header{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:20px;margin:16px 0 24px;padding:0 0 20px;border-bottom:1px solid var(--border)}
.ds-page-header h1{margin:4px 0 8px;font-size:clamp(25px,3vw,36px);letter-spacing:-.035em}
.ds-eyebrow{color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.ds-purpose{margin:0;max-width:640px;color:var(--text-secondary);font-size:14px}
.ds-context{margin-top:8px;color:var(--muted);font-size:12px}
.ds-overview-header{display:flex;justify-content:space-between;margin:12px 0 16px;padding:0;border:0}.ds-overview-header h1{font-size:22px;margin:0}
.ds-header-side{display:grid;gap:10px;justify-items:end}
.ds-page-guide{font-size:12px;color:var(--text-secondary)}
.ds-page-guide summary{display:inline-flex;align-items:center;min-height:44px;cursor:pointer;text-decoration:underline;text-underline-offset:3px}
.ds-page-guide[open]{padding-bottom:8px}.ds-page-guide .ds-freshness{display:block;font-size:12px;margin-top:8px}
.league-standings{display:grid;gap:8px}
.league-standing{display:grid;grid-template-columns:36px minmax(0,1fr) auto 12px;gap:10px;align-items:center;padding:14px 12px;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--text);text-decoration:none}
.league-standing:hover{border-color:var(--accent)}.league-franchise{display:grid;gap:5px;min-width:0}.league-franchise b{font-size:15px;overflow-wrap:anywhere}.league-franchise>span{font-size:12px;color:var(--text-secondary)}
.league-place{display:grid;place-items:center;width:34px;height:34px;border:1px solid var(--border);border-radius:50%;font-weight:800}.league-place.rank-1{color:#e8c76a;border-color:#8b7440;background:#282518}.league-place.rank-2{color:#d0dce5;border-color:#66737c;background:#20292e}.league-place.rank-3{color:#dba778;border-color:#805a3c;background:#2b211b}.league-points{font-size:12px;color:var(--blue);font-variant-numeric:tabular-nums}
.franchise-portrait{position:relative;display:grid;place-items:center;width:64px;height:64px;flex:0 0 64px;border-radius:14px;background:var(--surface-interactive);color:var(--accent);font-size:23px;font-weight:750;overflow:hidden}
.franchise-portrait img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:var(--surface-interactive)}
.team-head{display:flex;align-items:center;gap:12px}.team-head>div:not(.rank-badge){flex:1;min-width:0}.team-head .franchise-name{font-size:22px;overflow-wrap:anywhere}.team-open{display:flex;justify-content:space-between;align-items:center;min-height:44px;border-top:1px solid var(--border);color:var(--accent);font-weight:650}
.thq-identity>.franchise-portrait{width:88px;height:88px;flex-basis:88px;font-size:30px}
.market-hero{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:8px 0 16px;color:var(--text-secondary);font-size:13px}.market-hero p{margin:0}.market-hero b{color:var(--blue)}
.market-value[data-availability="unavailable"]{font-size:14px;color:var(--text-secondary);font-weight:550;max-width:120px}
.ti-impact-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:12px 18px;border-top:1px solid var(--border)}.ti-impact-strip>div{display:grid;align-content:start;gap:6px}.ti-impact-strip span{font-size:11px;color:var(--text-secondary)}.ti-impact-strip b{font-size:11px;color:var(--text);overflow-wrap:anywhere;font-weight:650}
@media(max-width:420px){.ti-impact-strip{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
.market-filters{display:grid;grid-template-columns:2fr repeat(3,1fr) auto;gap:10px;align-items:end;padding:12px 0;border:0;background:transparent;box-shadow:none}.market-filters h3{grid-column:1/-1;margin:0}.market-filters label{display:grid;gap:5px;font-size:12px}
.market-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.market-asset{position:relative;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px 12px;align-items:center;padding:16px;border:1px solid var(--border);border-radius:16px;background:var(--surface)}
.market-rank{display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:var(--surface-interactive);color:var(--text-secondary);font-weight:700}.market-owner{grid-column:2;color:var(--muted);font-size:12px}.market-value{grid-column:3;grid-row:1/3;text-align:right;color:var(--blue);font-size:23px;font-weight:750}.market-value small{display:block;color:var(--muted);font-size:11px;text-transform:uppercase}.market-context{grid-column:2/4;padding-top:10px;border-top:1px solid var(--border);color:var(--muted);font-size:12px}.market-open{grid-column:1/4;text-align:right;color:var(--accent);font-weight:650;min-height:44px;display:flex;align-items:center;justify-content:flex-end}
nav[aria-label="Market pagination"]{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0}nav[aria-label="Market pagination"] a{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;border:1px solid var(--border);border-radius:8px}
@media(max-width:760px){.market-filters{grid-template-columns:1fr 1fr}.market-filters h3,.market-filters label:first-of-type,.market-filters button{grid-column:1/-1}.market-grid{grid-template-columns:1fr}.market-asset{padding:12px;gap:8px}.market-rank{width:26px;height:26px;font-size:12px}}
.ds-freshness{font-size:11px;color:var(--muted);text-align:right;max-width:220px;overflow-wrap:anywhere}
.ds-freshness b{font-weight:500}
.ds-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.ds-action,.ux-primary-action,.ux-secondary-action{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:10px 16px;font-size:13px;font-weight:700;border:1px solid var(--border);border-radius:var(--radius-sm)}
.ds-action:hover,.ux-secondary-action:hover{background:var(--surface-interactive)}
.ds-action.primary,.ux-primary-action,.btn{background:linear-gradient(110deg,var(--accent),var(--accent-strong));color:#0c1908;border-color:var(--accent)}
.ds-action.primary:hover,.ux-primary-action:hover{background:var(--accent)}
.ds-recommendation{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;padding:20px;border:1px solid #365334;border-radius:var(--radius-lg);background:var(--surface)}
.ds-recommendation h2{font-size:22px;margin:8px 0}
.ds-recommendation p{color:var(--text-secondary);max-width:760px}
.ds-confidence{text-align:right;font-size:12px;color:var(--muted)}
.ds-confidence b{display:block;color:var(--positive);font-size:22px}
.ds-recommendation details{grid-column:1/-1;border-top:1px solid var(--border);padding-top:12px}
.ds-recommendation summary,.ds-evidence summary{cursor:pointer;font-size:13px;color:var(--text-secondary)}
.ds-empty{padding:24px;border:1px solid var(--border);border-radius:var(--radius-lg);color:var(--muted);background:var(--surface);line-height:1.6}
.ds-empty b{display:block;color:var(--text);font-size:18px;margin-bottom:8px}
.ds-grade-context{font-size:12px;color:var(--muted);line-height:1.5}
.ds-breadcrumbs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px;font-size:13px;color:var(--muted)}
.ds-breadcrumbs a{color:var(--accent)}
.ds-breadcrumbs[aria-label="FOIS sections"]{gap:8px;border-bottom:1px solid var(--border);padding-bottom:8px}.ds-breadcrumbs[aria-label="FOIS sections"] a{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;border-radius:8px;background:var(--surface)}
.fois-count{color:var(--text-secondary);font-size:13px}.fois-count b{color:var(--blue);font-size:20px}
.fois-rank b{display:grid;place-items:center;border-radius:50%;width:44px;height:44px;border:1px solid var(--border)}
.fois-leader[data-fois-rank="1"] .fois-rank b{color:var(--gold);border-color:#8b7440}.fois-leader[data-fois-rank="2"] .fois-rank b{color:#d0dce5;border-color:#66737c}.fois-leader[data-fois-rank="3"] .fois-rank b{color:#dba778;border-color:#805a3c}
.ux-section{margin:28px 0}
.ux-section-head{display:flex;justify-content:space-between;align-items:baseline;gap:16px;margin-bottom:12px}
.ux-section-head h2{font-size:22px;margin:0;letter-spacing:-.025em}
.ux-section-head p{margin:0;color:var(--muted);font-size:12px}
.ux-command-grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(240px,.8fr);gap:16px}
.ux-feature{padding:24px;border:1px solid #365334;border-radius:var(--radius-lg);background:linear-gradient(120deg,var(--surface-elevated),var(--surface));position:relative}
.ux-feature h2{margin:8px 0;font-size:clamp(28px,4vw,42px);letter-spacing:-.04em}
.ux-feature-copy{font-size:15px;line-height:1.6;max-width:620px;color:var(--text-secondary)}
.ux-feature-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
.ux-signal-rail{display:grid;align-content:start;gap:8px}
.ux-signal{display:grid;grid-template-columns:36px 1fr auto;gap:10px;align-items:center;padding:12px 0;border-bottom:1px solid var(--border)}
.ux-signal-icon{display:grid;place-items:center;width:32px;height:32px;color:var(--accent);font-size:20px}
.ux-signal b,.ux-signal small{display:block}.ux-signal small{color:var(--muted)}
.ux-action-list{display:grid;gap:8px}
.ux-action{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--surface)}
.ux-action p{margin:4px 0 0;color:var(--muted);font-size:13px}
.ux-recap{border-left:3px solid var(--accent);line-height:1.65}
.ux-recap p{max-width:760px}
.ux-answer{border-left:3px solid var(--accent)}
.technical-details{margin-top:12px}.technical-details>summary{cursor:pointer;color:var(--muted);font-size:12px}
.evidence-unavailable{padding:14px;border:1px dashed var(--border);border-radius:var(--radius-md);color:var(--muted)}
.player-summary{display:flex;align-items:center;gap:12px;min-width:0}
.player-portrait{position:relative;flex:0 0 52px;width:52px;height:52px}
.player-headshot,.player-headshot-fallback{position:absolute;inset:0;width:52px;height:52px;border-radius:10px}
.player-headshot{z-index:1;object-fit:cover;object-position:top;background:var(--surface-interactive)}
.player-headshot-fallback{display:grid;place-items:center;background:var(--surface-interactive);color:var(--accent);font-weight:700}
.player-summary-copy{min-width:0}.player-summary-copy b{display:block;font-size:14px;font-weight:650}
.player-summary-copy span{display:block;font-size:12px;color:var(--muted)}
a:has(>.player-summary):hover .player-summary-copy b{color:var(--accent)}
.score-row{display:grid;gap:4px}.score-row small{font-size:12px;color:var(--muted)}
.score-row.primary b{font-size:28px;color:var(--blue)}.score-row.supporting b{font-size:14px}
.score-row[data-dtos-availability="unavailable"] b{font-size:15px;line-height:1.4;color:var(--text-secondary);font-weight:550}
.scoreboard{grid-template-columns:minmax(0,1fr) auto minmax(0,1fr)}.scoreboard-team{overflow-wrap:anywhere}.scoreboard-team a{display:inline-flex;align-items:center;min-height:44px}
.podium-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.podium-card{display:block;padding:18px;border:1px solid var(--border);border-radius:var(--radius-lg);background:var(--surface)}
.podium-card[data-rank="1"]{border-color:#8c713e}.podium-card[data-rank="2"]{border-color:#697681}.podium-card[data-rank="3"]{border-color:#835c45}
.podium-rank{display:inline-grid;place-items:center;width:36px;height:36px;border-radius:50%;background:var(--surface-interactive);color:var(--gold);font-size:16px;font-weight:750}
.podium-card h3{margin:12px 0 4px;font-size:18px}.podium-card p{margin:0;color:var(--muted)}
.status-trophy{display:inline-flex;gap:6px;align-items:center;color:var(--gold);font-weight:700}
.status-trophy:before{content:"🏆"}.status-hot{color:#ffac73;font-weight:700}.status-hot:before{content:"🔥";margin-right:6px}
.ds-table-wrap{max-width:100%;overflow-x:auto}
.ds-table-wrap:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
.season-card h3{font-size:36px;margin:8px 0;color:var(--blue)}.season-card p{font-size:14px}.season-action{display:block;margin-top:18px;color:var(--accent);font-weight:650}
.season-podium{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:14px;margin:20px 0}.season-champion,.season-runner-up{padding:22px;border:1px solid var(--border);border-radius:16px;background:var(--surface)}.season-champion:has(.status-trophy){border-color:#8b7440;background:linear-gradient(120deg,#211e14,var(--surface))}.season-champion h3{font-size:26px;line-height:1.3;margin:12px 0 0;overflow-wrap:anywhere}.season-runner-up{display:grid;align-content:center;gap:10px}.season-runner-up>span{font-size:12px;color:var(--muted)}.season-runner-up>b{font-size:18px}.season-counts{color:var(--muted);font-size:13px}.season-counts b{color:var(--blue)}
@media(max-width:600px){.season-podium{grid-template-columns:1fr}.season-runner-up{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px}}
.matchup-card,.matchup-hero,.battle-card,.bench-total-card{background:var(--surface);border-color:var(--border);box-shadow:none}
.matchup-card .versus{padding:12px 0}.scoreboard-team a:hover{color:var(--accent)}
.battle-owner,.battle-player span,.bench-player span{font-size:12px}.starter-projections small{font-size:11px}.starter-projections b{font-size:16px}
.matchup-player-link{display:flex;min-height:44px;align-items:center;color:inherit;text-decoration:none;border-radius:10px}
.matchup-player-link:hover{background:rgba(126,223,64,.08)}
.matchup-player-link:focus-visible{outline:2px solid var(--accent,#80df40);outline-offset:3px}
.battle-side,.bench-player{background:var(--background);border-color:var(--border)}
.pick-asset-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:20px 0}
.pick-asset-title{display:flex;gap:12px;align-items:center;min-height:52px}.pick-asset-title b{font-size:18px}.pick-asset-title small{display:block;color:var(--accent);font-size:12px}
.pick-emblem{display:grid;place-items:center;width:44px;height:48px;border:1px solid #776443;border-radius:8px 8px 18px 18px;color:var(--gold);font-weight:700;flex-shrink:0}
.pick-owner{margin:14px 0;font-size:14px}.pick-owner span{display:block;font-size:12px;color:var(--muted)}.pick-owner a:hover{color:var(--accent)}
.pick-outlook{display:flex;justify-content:space-between;align-items:center;gap:10px;padding-top:12px;border-top:1px solid var(--border)}.pick-outlook b{color:var(--blue);font-size:22px}.pick-outlook span{font-size:12px;color:var(--muted)}
.card-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:20px 0}
.fois-leaderboard{gap:14px}.fois-leader{grid-template-columns:52px minmax(150px,1.2fr) 80px minmax(150px,1fr);gap:16px;border-left:3px solid var(--border)}
.fois-leader[data-fois-rank="1"]{border-left-color:var(--gold)}
.fois-leader[data-fois-rank="2"]{border-left-color:#b7c5cf}
.fois-leader[data-fois-rank="3"]{border-left-color:#cb936d}
.fois-leader>div:nth-of-type(5){grid-column:2/4;font-size:13px;color:var(--text-secondary)}
.fois-leader>.ds-action{grid-column:4;justify-self:stretch}
.fois-leader h3{font-size:20px;margin:4px 0}.fois-leader p{margin:4px 0}
.fois-score b{color:var(--blue);font-size:28px}.fois-score span{font-size:16px}
.fois-evidence span{font-size:12px}.fois-evidence b{font-size:13px;color:var(--text-secondary)}
.fois-rank span{font-size:11px}.fois-rank b{font-size:25px}
.metric-grid,.summary-grid{gap:12px}.metric{background:var(--surface);padding:14px;border-color:var(--border)}
.metric b{color:var(--blue);font-size:23px}.metric span{font-size:12px}
.empty-state{padding:24px;border:1px solid var(--border);border-radius:var(--radius-lg);background:var(--surface)}
.empty-state h2{font-size:23px}.empty-state p{color:var(--text-secondary)}
@media(max-width:760px){
 .pick-asset-grid{grid-template-columns:1fr}
 .card-grid{grid-template-columns:1fr}
 .fois-leader{grid-template-columns:40px minmax(0,1fr) 65px;gap:10px}
 .fois-leader>.ds-action,.fois-leader>div:nth-of-type(5),.fois-leader .fois-evidence{grid-column:2/4}
 .wrap{padding:12px 14px calc(88px + env(safe-area-inset-bottom))}
 .top{min-height:44px}.brand p{font-size:11px}
 .account-context summary{flex-wrap:wrap;gap:4px 10px}
 .manager-nav{position:fixed;z-index:30;left:0;right:0;bottom:0;margin:0;border:0;border-top:1px solid var(--border);padding:6px 6px calc(6px + env(safe-area-inset-bottom));background:#071017;box-shadow:0 -6px 20px rgba(0,0,0,.2)}
 .manager-nav a{flex-direction:column;gap:3px;min-height:52px;padding:5px 2px;font-size:11px;border-bottom:0;border-radius:8px}
 .nav-icon{width:24px;height:24px}
 .manager-nav a[aria-current=page]{background:rgba(128,223,66,.07)}
 .secondary-nav{margin:6px 0 12px}
 .ds-page-header{grid-template-columns:1fr;gap:12px;margin:12px 0 18px;padding-bottom:16px}
 .ds-page-header h1{font-size:27px}.ds-purpose{font-size:13px}
 .ds-header-side{justify-items:start;gap:8px}.ds-freshness{display:none}
 .ds-actions{justify-content:flex-start}.ds-action{min-height:44px}
 .ds-recommendation{grid-template-columns:1fr;padding:16px}
 .ds-confidence{text-align:left}.ds-confidence b{display:inline;margin-right:6px;font-size:18px}
 .ux-command-grid{grid-template-columns:1fr}.ux-feature{padding:20px}
 .ux-feature h2{font-size:30px}.ux-feature-copy{font-size:14px}
 .ux-feature-actions>.ux-primary-action{flex:1}
 .ux-section-head{display:block}.ux-section-head p{margin-top:4px}
 .ux-section{margin:24px 0}.ux-section-head h2{font-size:21px}
 .podium-grid{grid-template-columns:1fr}.podium-card{display:grid;grid-template-columns:36px 1fr;gap:4px 12px;padding:14px}
 .podium-rank{grid-row:1/3}.podium-card h3{margin:0}.podium-card p{grid-column:2}
 table{max-width:100%}
}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
"""
