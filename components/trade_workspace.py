"""One mobile/desktop workspace for all bilateral Trade Center entry paths."""
from html import escape


def trade_workspace(view: dict, workflow: str, asset_id=None, owner_roster_id=None) -> str:
    active = int(view["active_team"]["roster_id"])
    league = getattr(view.get("manager_context"), "league_id", "")
    titles = {"calculator": "Trade Calculator", "create": "Create Trade", "trade-for": "Trade For", "shop": "Shop Asset", "recommended": "Recommended Trades"}
    title = titles[workflow]
    calculator = workflow == 'calculator'
    strategy_open = '<details><summary>Strategy for advanced analysis</summary>' if calculator else ''
    strategy_close = '</details>' if calculator else ''
    market_panel = '<section id="trade-balance" class="ti-market-balance" aria-live="polite"></section>'
    calculator_panel = (f'<section class="tw-calculator" aria-label="Market calculator">{market_panel}<button id="trade-balance-offer" type="button" disabled>Balance offer · preview options</button><div class="ti-actions"><button id="trade-run" type="button" disabled>Advanced DTOS analysis</button><button id="calculator-protect" type="button">Protect assets</button></div><div class="tw-packages"><section><h4>Side A · You send</h4><div id="calculator-sent"></div></section><section><h4>Side B · You receive</h4><div id="calculator-received"></div></section></div><p class="muted">Use the searchable owned-asset lists below to add players and exact picks. Market totals update immediately.</p></section>' if calculator else '')
    market_detail = '' if calculator else f'<details class="tw-market-detail"><summary>Market Balance · acquisition-price evidence</summary>{market_panel}</details>'
    calculator_link = '' if calculator else f'<a class="ti-action" href="/trades/calculator?front_office={active}">Open this workspace in Calculator</a>'
    protect_control = '<button id="calculator-lock" type="button">Do not trade selected exact asset</button>' if calculator else ''
    recommended_controls = '''<section aria-label="Recommendation session"><label for="recommendation-filter">Opportunity filter</label><select id="recommendation-filter"><option value="all">All supported opportunities</option><option value="win_now">Win Now</option><option value="value">Value</option><option value="roster_fit">Roster Fit</option><option value="future">Draft Capital</option><option value="sell_high" disabled>Sell High — movement evidence unavailable</option></select><button id="recommendation-refresh" type="button">Show Next 5</button><p class="muted">Only evidence-backed opportunities qualify. Show Next 5 excludes prior idea families in this page session. Fewer than five are shown when fewer qualify.</p></section>''' if workflow == 'recommended' else ''
    shop_controls = '''<section aria-label="Shop search preferences"><label for="shop-preference">Search preference (this session only)</label>
<select id="shop-preference"><option value="best_overall">Best Overall Return</option><option value="win_now">Win-Now Help</option><option value="youth_rebuild">Youth / Rebuild</option><option value="draft_capital">Draft Capital</option><option value="position_need">Position Need</option><option value="custom">Custom — protect assets</option></select>
<label for="shop-position">Position for Position Need</label><select id="shop-position" disabled><option value="QB">QB</option><option value="RB">RB</option><option value="WR">WR</option><option value="TE">TE</option></select>
<label for="shop-protected">Keep these assets out of outgoing packages</label><select id="shop-protected" multiple aria-label="Protected outgoing assets"></select>
<p class="muted">Preferences order supported returns; they do not change the trade assessment. Age is not a longevity forecast. Custom uses the protected assets selected here.</p></section>''' if workflow == 'shop' else ''
    partner_placeholder = 'All eligible teams' if workflow == 'shop' else 'Choose a trade partner'
    adjustments = "".join(
        f'<button type="button" data-adjust="{escape(label.lower(), quote=True)}">{label}</button>'
        for label in (
            "Keep this player", "Do not trade this pick", "Replace this asset",
            "Use WRs instead", "Use RBs instead", "Use picks instead", "Add a pick",
            "Get another player back", "Make it cheaper", "Make it younger",
            "Make it more win-now", "Expand the trade",
            "Make this trade work", "Alternative construction", "Alternative target",
        )
    )
    return f'''<link rel="stylesheet" href="/static/css/trade_workspace.css">
<section class="card ti-hero"><div><div class="identity-kicker">Trade Center · {escape(title)}</div><h2>{escape(title)}</h2><p>Choose a partner. Build your proposal. Review the intelligence.</p></div><a class="ti-action" href="/trades?front_office={active}">All Trade Workflows</a></section>
<section id="trade-builder" class="card tw-workspace" data-trade-workflow="{workflow}" data-front-office="{active}" data-league="{escape(league, quote=True)}" data-preload-asset="{escape(str(asset_id or ''), quote=True)}" data-owner-roster="{int(owner_roster_id or 0)}">
<label for="trade-partner">Counterparty</label><select id="trade-partner"><option value="">{partner_placeholder}</option></select>
{strategy_open}<label for="trade-strategy">Your strategy</label><select id="trade-strategy"><option value="">Use supported competitive window</option><option value="WIN NOW">WIN NOW</option><option value="RETOOL">RETOOL</option><option value="REBUILD">REBUILD</option></select>{strategy_close}
<p id="trade-context" class="muted">Loading current league assets…</p>
<section id="trade-target" class="tw-target" hidden aria-label="Selected trade target"></section>
{shop_controls}
{recommended_controls}
{calculator_panel}
<div id="trade-board"><div class="tw-side-tabs" role="group" aria-label="Asset side"><button type="button" data-side="sent" aria-pressed="true">My assets</button><button type="button" data-side="received" aria-pressed="false">Their assets</button></div>
<div class="tw-boards"><section id="trade-sent-board"></section><section id="trade-received-board"></section></div></div>
<section id="trade-review" tabindex="-1" hidden><h3>Your proposal</h3><div class="tw-packages"><section><h4>You send</h4><div id="trade-sent-chips"></div></section><section><h4>You receive</h4><div id="trade-received-chips"></div></section></div></section>
<div class="ti-actions"><button id="trade-view" type="button">View Trade</button>{'' if calculator else '<button id="trade-run" type="button">Evaluate Trade</button>'}<button id="trade-edit" type="button">Edit Trade</button><button id="trade-adjust" type="button">Adjust Offer / protect assets</button><button id="trade-find" type="button" hidden>Find Bilateral Options</button>{calculator_link}</div>
<section id="trade-assist" hidden><label for="trade-instruction">How should DTOS adjust it?</label><input id="trade-instruction" maxlength="300" placeholder="Make it cheaper, or name an asset to protect"><label for="trade-constraint-asset">Exact asset to keep or replace</label><select id="trade-constraint-asset"><option value="">Choose a specific owned asset</option></select>{protect_control}<button id="trade-release-lock" type="button">Remove selected adjustment lock</button><p>Keep and replace controls apply to this exact identity. Alternatives are previews; your proposal changes only when you adopt one.</p><details><summary>More adjustment options</summary><div class="ti-actions">{adjustments}</div></details><button id="trade-apply-adjust" type="button">Preview revised offers</button><button id="trade-alternatives" type="button">Preview alternatives</button></section>
<button id="trade-build-own" type="button" {'hidden' if workflow == 'create' else ''}>Build My Own</button>
<section id="trade-result" role="status" aria-live="polite" tabindex="-1" hidden></section>
{market_detail}
<div id="trade-tray" class="tw-tray" hidden><span id="trade-tray-text"></span><button id="trade-tray-view" type="button">View Trade</button></div>
<p class="muted">Ownership is revalidated before evaluation. Market Balance is neutral market evidence, not the recommendation. DTOS evaluates proposals; it does not send trades to Sleeper.</p></section><script src="/static/js/trade_workspace.js" defer></script>'''
