"""Source-independent public presentation over one reviewed fictional export.

No account, runtime, provider, Market, solver or Trade service is read here.
The router may retain the returned immutable HTML for all public requests.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
import json
import math
from pathlib import Path
from typing import Any

from src.ui.theme import DESIGN_SYSTEM_CSS


PUBLIC_WELCOME_CSS = """
body.public-welcome{margin:0;font-size:16px;color:var(--text-primary);line-height:1.55}
.public-welcome *{box-sizing:border-box}.public-welcome :is(h1,h2,h3,p,ul,ol,dl){overflow-wrap:anywhere}
.public-welcome .pw-wrap{width:min(100%,1160px);margin:0 auto;padding:0 24px 32px;min-width:0}
.public-welcome .pw-header{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:76px;border-bottom:1px solid var(--border)}
.public-welcome .pw-brand{display:inline-flex;align-items:center;min-height:44px;font-size:24px;font-weight:800;letter-spacing:.1em}
.public-welcome .pw-brand-d{color:var(--accent)}
.public-welcome .pw-action{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:9px 16px;border:1px solid var(--border);border-radius:8px;font-weight:700;font-size:14px;text-align:center}
.public-welcome .pw-action:hover{background:var(--surface-interactive)}
.public-welcome .pw-primary{background:var(--accent);border-color:var(--accent);color:#0c1908}.public-welcome .pw-primary:hover{background:var(--accent)}
.public-welcome a:focus-visible,.public-welcome summary:focus-visible,.public-welcome [tabindex]:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
.public-welcome .pw-skip{position:absolute;left:16px;top:-100px;z-index:1;background:var(--surface);padding:10px 16px;min-height:44px;border:1px solid var(--focus);border-radius:8px}.public-welcome .pw-skip:focus{top:8px}
.public-welcome .pw-intro{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:48px;padding:32px 0}
.public-welcome .pw-hero{min-width:0}.public-welcome .pw-eyebrow{font-size:12px;color:var(--accent);font-weight:750;letter-spacing:.08em;text-transform:uppercase;margin:0 0 12px}
.public-welcome h1{font-size:clamp(28px,3.7vw,42px);line-height:1.13;letter-spacing:-.035em;margin:0 0 18px;max-width:15ch}
.public-welcome .pw-value{color:var(--text-secondary);margin:0 0 20px;max-width:42ch;font-size:17px}
.public-welcome .pw-beta{color:var(--text-secondary);font-size:13px;max-width:43ch;margin:12px 0 0}
.public-welcome .pw-demo-group{min-width:0;scroll-margin-top:16px}.public-welcome .pw-demo-nav{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:0 0 10px}
.public-welcome .pw-demo-nav a{display:flex;align-items:center;justify-content:center;min-height:44px;padding:6px;border-bottom:1px solid var(--border);font-size:13px;font-weight:650;color:var(--text-secondary);text-align:center}
.public-welcome .pw-demo-nav a:hover{color:var(--accent)}
.public-welcome .pw-demo{border-top:1px solid var(--border);padding:0 0 10px;scroll-margin-top:16px}
.public-welcome .pw-demo>summary{min-height:58px;padding:12px 0;list-style:disclosure-closed inside;cursor:pointer}
.public-welcome .pw-demo[open]>summary{list-style-type:disclosure-open}
.public-welcome .pw-demo>summary h2{display:inline;font-size:20px;line-height:1.3;letter-spacing:-.02em;margin:0}
.public-welcome .pw-index{font-size:12px;color:var(--accent);font-weight:700;margin-right:8px;vertical-align:middle}
.public-welcome .pw-demo-note{font-size:12px;color:var(--text-secondary);margin:0 0 12px}
.public-welcome .pw-conclusion{background:var(--surface);border-left:3px solid var(--accent);border-radius:0 12px 12px 0;padding:16px;margin:0 0 14px}
.public-welcome h3{font-size:21px;line-height:1.3;margin:0 0 12px;letter-spacing:-.02em}
.public-welcome .pw-conclusion p{margin:9px 0;color:var(--text-secondary);font-size:14px}.public-welcome .pw-conclusion p:last-child{margin-bottom:0}
.public-welcome .pw-team-name{font-size:12px;font-weight:700;color:var(--accent);margin:0 0 8px}
.public-welcome .pw-number{font-size:27px;font-weight:750;color:var(--value-color);font-variant-numeric:tabular-nums;line-height:1.2}
.public-welcome .pw-metric-label{display:block;font-size:12px;color:var(--text-secondary);font-weight:450;margin-top:4px}
.public-welcome .pw-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:12px 0}
.public-welcome .pw-metrics>div{min-width:0}.public-welcome .pw-cost{border-left:2px solid var(--warning);padding-left:10px}
.public-welcome .pw-detail{font-size:14px;margin:8px 0 12px}.public-welcome .pw-detail>summary{min-height:44px;padding:8px 0;color:var(--text-secondary);cursor:pointer}
.public-welcome .pw-detail p{font-size:14px;color:var(--text-secondary)}
.public-welcome .pw-roster{list-style:none;padding:0;margin:0}.public-welcome .pw-roster li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:9px 0;border-top:1px solid var(--border);align-items:center}
.public-welcome .pw-asset{display:flex;align-items:center;gap:9px;min-width:0}.public-welcome .pw-position{display:inline-flex;align-items:center;justify-content:center;flex:0 0 38px;min-height:32px;padding:3px;border-radius:7px;background:var(--surface-elevated);font-size:11px;color:var(--text-secondary);font-weight:750}
.public-welcome .pw-asset-copy{min-width:0;font-size:14px;font-weight:650}.public-welcome .pw-asset-copy small{display:block;color:var(--text-secondary);font-size:12px;font-weight:450}.public-welcome .pw-points{color:var(--value-color);font-variant-numeric:tabular-nums;font-size:14px;text-align:right}
.public-welcome .pw-capital{padding-left:20px}.public-welcome .pw-capital li{margin:8px 0}.public-welcome .pw-capital small{display:block;color:var(--text-secondary);font-size:12px}
.public-welcome .pw-package{padding:12px 0;border-top:1px solid var(--border)}.public-welcome .pw-package h3{font-size:14px;margin:0 0 8px;color:var(--text-secondary)}
.public-welcome .pw-package ul{padding:0;margin:0;list-style:none}.public-welcome .pw-package li+li{margin-top:8px}
.public-welcome .pw-side{padding:12px 0;border-top:1px solid var(--border)}.public-welcome .pw-side h3{font-size:16px;margin:0 0 6px}.public-welcome .pw-side p{font-size:14px;color:var(--text-secondary);margin:8px 0}
.public-welcome .pw-side .pw-delta{color:var(--positive);font-weight:750;font-variant-numeric:tabular-nums}
.public-welcome .pw-assessment{font-size:14px;color:var(--text-primary);margin:12px 0}.public-welcome .pw-assessment small{display:block;color:var(--text-secondary);font-size:12px;margin-top:4px}
.public-welcome .pw-comparison{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:12px 0}.public-welcome .pw-comparison>div{min-width:0;border-top:1px solid var(--border);padding:12px 0}.public-welcome .pw-comparison h3{font-size:14px;margin:0 0 9px}.public-welcome .pw-comparison dl{margin:0}.public-welcome .pw-comparison dt{font-size:12px;color:var(--text-secondary)}.public-welcome .pw-comparison dd{margin:2px 0 8px;font-size:21px;font-weight:750;font-variant-numeric:tabular-nums;color:var(--value-color)}
.public-welcome .pw-ranking{padding-left:24px;font-size:14px}.public-welcome .pw-ranking li{margin:8px 0}.public-welcome .pw-ranking span{color:var(--text-secondary)}
.public-welcome .pw-scoring{margin:0;padding-left:20px}.public-welcome .pw-scoring li{margin:6px 0}
.public-welcome .pw-setup{border-top:1px solid var(--border);padding:24px 0}.public-welcome .pw-setup h2{font-size:23px;line-height:1.3;margin:0 0 12px}.public-welcome .pw-setup p{max-width:70ch;color:var(--text-secondary)}
.public-welcome .pw-account-actions{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.public-welcome .pw-access-note{font-size:13px}.public-welcome .pw-footer{border-top:1px solid var(--border);padding-top:16px;color:var(--text-secondary);font-size:12px}
.public-welcome :target{scroll-margin-top:16px}
@media(max-width:760px){.public-welcome .pw-wrap{padding:0 16px 24px}.public-welcome .pw-header{min-height:66px}.public-welcome .pw-intro{grid-template-columns:minmax(0,1fr);gap:22px;padding:22px 0}.public-welcome h1{font-size:28px;max-width:18ch;margin-bottom:14px}.public-welcome .pw-value{font-size:16px;margin-bottom:16px}.public-welcome .pw-hero>.pw-primary{width:100%}.public-welcome .pw-conclusion{padding:13px}.public-welcome .pw-account-actions{display:grid;grid-template-columns:1fr}.public-welcome .pw-demo>summary h2{font-size:19px}.public-welcome .pw-number{font-size:25px}}
@media(prefers-reduced-motion:reduce){.public-welcome{scroll-behavior:auto}}
"""


def _text(value: Any) -> str:
    return escape(str(value))


def _number(value: Any, *, signed: bool = False) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "Unavailable"
    if value == 0:
        return "0"
    result = f"{value:,.2f}".rstrip("0").rstrip(".")
    return ("+" if signed and value > 0 else "") + result


def _asset(row: Mapping[str, Any], *, slot: bool = False) -> str:
    position = _text(row.get("position") or "PICK")
    label = _text(row.get("name") or row["label"])
    detail = f'<small>Starting slot: {_text(row["slot"])}</small>' if slot and row.get("slot") else ""
    return (f'<span class="pw-asset"><span class="pw-position">{position}</span>'
            f'<span class="pw-asset-copy">{label}{detail}</span></span>')


def _roster(rows: list[Mapping[str, Any]], *, starters: bool = False) -> str:
    return '<ul class="pw-roster">' + "".join(
        f'<li>{_asset(row, slot=starters)}<span class="pw-points">{_number(row.get("points"))} pts</span></li>'
        for row in rows
    ) + '</ul>'


def _capital(rows: list[Mapping[str, Any]] | None) -> str:
    if rows is None:
        return '<p>Draft-capital evidence is unavailable in this example.</p>'
    if not rows:
        return '<p>This fictional roster owns no draft picks in the example.</p>'
    return '<ul class="pw-capital">' + "".join(
        f'<li><b>{_text(row["label"])}</b><small>Original franchise: {_text(row["original_franchise"])}'
        f' · Current owner: {_text(row["current_owner"])}</small></li>' for row in rows
    ) + '</ul>'


def _ranking(rows: list[Mapping[str, Any]]) -> str:
    values = []
    for row in rows:
        rank = row["rank"]
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            raise ValueError("The reviewed ranking excerpt needs positive integer positions.")
        values.append(f'<li value="{rank}">{_text(row["label"])} <span>· {_number(row.get("value"))} personal units</span></li>')
    return '<ol class="pw-ranking">' + "".join(values) + '</ol>'


def _side(side: Mapping[str, Any]) -> str:
    return (f'<section class="pw-side"><h3>{_text(side["name"])}</h3>'
            f'<p><span class="pw-delta">{_number(side.get("delta"), signed=True)} projected points</span>'
            f' · strongest legal lineup {_number(side.get("before"))} → {_number(side.get("after"))}</p>'
            f'<p><b>Benefit:</b> {_text(side["benefit"])}</p>'
            f'<p class="pw-cost"><b>Cost:</b> {_text(side["cost"])}</p></section>')


_SCORING_LABELS = {"pass_yd": "Passing yard", "pass_td": "Passing touchdown", "pass_int": "Interception thrown",
                   "rush_yd": "Rushing yard", "rush_td": "Rushing touchdown", "rec": "Reception",
                   "rec_yd": "Receiving yard", "rec_td": "Receiving touchdown", "fum_lost": "Fumble lost"}


def render_welcome(data: Mapping[str, Any] | None = None) -> str:
    """Return identical public HTML for every viewer; only frozen fictional facts.

    The optional mapping is an explicit validation seam, never a request input.
    No personalized preferences or live source service is accepted here.
    """
    if data is None:
        data = json.loads(Path(__file__).with_name("public_demo_data.json").read_text(encoding="utf-8"))
    team, trade, personal, league = (data[key] for key in ("team", "trade", "personal", "league"))
    demo_note = '<p class="pw-demo-note">Demonstration data · fictional league · not current player advice.</p>'
    packages = "".join(
        f'<section class="pw-package"><h3>{title}</h3><ul>'
        + "".join(f'<li>{_asset(row)}</li>' for row in rows) + '</ul></section>'
        for title, rows in (("You Send", trade["send"]), ("You Receive", trade["receive"]))
    )
    eligibility = "Eligible in this fictional evaluation" if trade.get("eligible") is True else "Not eligible as a generated recommendation"
    rank = team.get("comparison_rank")
    population = team.get("comparison_population")
    qualified_rank = (isinstance(rank, int) and not isinstance(rank, bool) and isinstance(population, int)
                      and not isinstance(population, bool) and 0 < rank <= population)
    rank_context = (f'Week {_text(data["week"])}: projected lineup #{rank} among {population} supported fictional franchises. This is not official standing.'
                    if qualified_rank else 'A comparative lineup rank is unavailable for this example.')
    market_totals = (f'<div class="pw-metrics"><div><b class="pw-number">{_number(trade.get("market_sent"))}</b>'
                     '<span class="pw-metric-label">You send · neutral Market units</span></div>'
                     f'<div><b class="pw-number">{_number(trade.get("market_received"))}</b>'
                     '<span class="pw-metric-label">You receive · neutral Market units</span></div></div>')
    reserve_text = "; ".join(f'{_text(row.get("name") or row["label"])} ({_text(row["position"])}): {_number(row.get("points"))} projected points' for row in team["reserve"])
    comparison = "".join(
        f'<div><h3>{title}</h3><dl><dt>You Send</dt><dd>{_number(personal.get(sent))}</dd>'
        f'<dt>You Receive</dt><dd>{_number(personal.get(received))}</dd></dl></div>'
        for title, sent, received in (("Neutral DTOS · Market units", "neutral_sent", "neutral_received"),
                                      ("Custom DTOS · personal units", "personal_sent", "personal_received"))
    )
    scoring = "".join(f'<li>{_text(_SCORING_LABELS.get(key, key.replace("_", " ")))}: {_number(value)} points</li>'
                      for key, value in league["scoring"].items())
    limitations = "".join(f'<li>{_text(item)}</li>' for item in data["limitations"])
    unchanged = "".join(f'<li>{_text(item)}</li>' for item in personal["unchanged"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="DTOS helps dynasty managers understand their roster, compare both sides of a trade, and use personal rankings alongside neutral Market values.">
<title>DTOS · Your dynasty front office</title><style>{DESIGN_SYSTEM_CSS}\n{PUBLIC_WELCOME_CSS}</style></head>
<body class="public-welcome"><a class="pw-skip" href="#main">Skip to main content</a><div class="pw-wrap">
<header class="pw-header"><a class="pw-brand" href="/welcome" aria-label="DTOS welcome"><span class="pw-brand-d" aria-hidden="true">D</span><span>TOS</span></a><a class="pw-action" href="/account/sign-in">Sign In</a></header>
<main id="main" tabindex="-1"><div class="pw-intro"><section class="pw-hero" aria-labelledby="welcome-title">
<p class="pw-eyebrow">Dynasty football · Sleeper</p><h1 id="welcome-title">A clearer view of your dynasty.</h1>
<p class="pw-value">Understand your team, weigh both sides of a trade, and bring your own player values.</p>
<a class="pw-action pw-primary" href="#demo">Explore the Demo</a>
<p class="pw-beta">Controlled beta · Participation remains limited. Existing participants can sign in.</p>
</section><section class="pw-demo-group" id="demo" tabindex="-1" aria-label="Read-only product demonstrations">
<nav class="pw-demo-nav" aria-label="Explore the demonstrations"><a href="#demo-team">Team</a><a href="#demo-trade">Trade</a><a href="#demo-values">Your values</a></nav>
<details class="pw-demo" id="demo-team" open><summary><h2><span class="pw-index">01</span>Understand Your Team</h2></summary>
{demo_note}<article class="pw-conclusion"><p class="pw-team-name">{_text(team["name"])} · {_text(league["name"])}</p>
<h3>{_text(team["strength"])}</h3><div class="pw-metrics"><div><b class="pw-number">{_number(team.get("lineup_points"))}</b><span class="pw-metric-label">Strongest legal lineup · projected points</span></div><div><b>{_text(team["strategy"])}</b><span class="pw-metric-label">Selected goal in this example</span></div></div>
<p>{rank_context}</p><p><b>Replacement evidence:</b> {reserve_text or "No supported replacement observations in this example."}</p><p class="pw-cost"><b>Keep in mind:</b> {_text(team["limitation"])}</p><p><b>Consider next:</b> {_text(team["next_step"])}</p></article>
<details class="pw-detail" id="demo-roster"><summary>Starting lineup and useful replacements</summary><p>Fictional week {_text(data["week"])} projections under this example's rules. Bench players are not counted in the starting total.</p><h3>Starting lineup</h3>{_roster(team["lineup"], starters=True)}<h3>Available replacements</h3>{_roster(team["reserve"])}</details>
<details class="pw-detail" id="demo-capital"><summary>Exact draft capital</summary>{_capital(team.get("capital"))}<p>Original franchise and current ownership remain separate. A pick is not guaranteed to be early or to produce a particular player.</p></details>
</details>
<details class="pw-demo" id="demo-trade"><summary><h2><span class="pw-index">02</span>Make Better Trades</h2></summary>
{demo_note}<p class="pw-team-name">Hypothetical offer · {_text(trade["active"]["name"])} and {_text(trade["partner"]["name"])}</p>
{packages}{market_totals}<p class="pw-assessment"><b>{_text(trade.get("recommendation") or "Overall assessment unavailable")}</b><small>{eligibility}. {_text(trade["qualification"])}</small></p>
{_side(trade["active"])}{_side(trade["partner"])}<p class="pw-demo-note">A plausible offer is not a prediction that the other manager will accept. Projected gains are not guaranteed results.</p>
</details>
<details class="pw-demo" id="demo-values"><summary><h2><span class="pw-index">03</span>Build Your Own DTOS</h2></summary>
{demo_note}<p class="pw-team-name">The same hypothetical offer · {_text(trade["active"]["name"])}</p><p>Your ranking changes your view of this offer. Personal values can differ while neutral Market prices and the other manager's valuations stay unchanged.</p><p class="pw-demo-note">A read-only excerpt from the full example ranking, not an editor. Unpriced future picks remain capital facts; they are not assigned invented personal prices.</p>
<div class="pw-comparison">{comparison}</div><p class="pw-cost">{_text(personal["limitation"])}</p>
<details class="pw-detail"><summary>See the ranking move and what stays unchanged</summary><p>{_text(personal["explanation"])}</p><p>{_text(personal["cohort_label"])}</p><h3>Before the personal move</h3>{_ranking(personal["before_order"])}<h3>After the personal move</h3>{_ranking(personal["after_order"])}<ul>{unchanged}</ul><p>In your own DTOS, you can save optional tiers, targets, players you prefer not to acquire, and specific assets to protect. Those opinions stay separate from temporary Trade choices. Custom values require compatible Market evidence; missing prices do not become zero.</p></details>
</details>
<details class="pw-detail" id="demo-evidence"><summary>Example scoring, source and limitations</summary><p>{_text(data["label"])} · {_text(data["season"])} · Week {_text(data["week"])}. {_text(league["scoring_label"])}</p><p>Required starting slots: {_text(", ".join(league["starter_slots"]))}.</p><ul class="pw-scoring">{scoring}</ul><ul>{limitations}</ul><p>Frozen fictional fixture: {_text(data["fixture_id"])} · version {_text(data["version"])}. No live analysis runs when you open or explore this page.</p></details>
</section></div>
<section class="pw-setup" aria-labelledby="setup-title"><h2 id="setup-title">Use DTOS with your Sleeper league</h2><p>Create your DTOS account, enter your public Sleeper username, then review your franchise match. Your DTOS account is separate from Sleeper; resolving a username does not independently prove control of that Sleeper account.</p><p><b>Already participating in the beta?</b> Use the existing account destinations below.</p><nav class="pw-account-actions" aria-label="Account destinations"><a class="pw-action" href="/account/sign-in">Sign In</a><a class="pw-action" href="/account/create">Create Account</a><a class="pw-action" href="/account/recover">Account Recovery</a></nav><p class="pw-access-note">Account creation is available. DTOS remains in a controlled beta with limited capacity. Creating an account does not change that capacity.</p></section>
</main><footer class="pw-footer">DTOS · Dynasty front office intelligence. Demonstrations use fictional data, not your league, saved rankings or current player advice.</footer></div></body></html>'''
