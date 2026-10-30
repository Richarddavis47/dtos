"""One mobile/desktop workspace for all bilateral Trade Center entry paths."""
from html import escape


def trade_workspace(view: dict, workflow: str, asset_id=None, owner_roster_id=None) -> str:
    active = int(view["active_team"]["roster_id"])
    league = getattr(view.get("manager_context"), "league_id", "")
    titles = {"calculator": "Trade Calculator", "create": "Build a Trade", "trade-for": "Trade For", "shop": "Shop Asset", "recommended": "Generate Trades"}
    title = titles[workflow]
    calculator = workflow == 'calculator'
    market_editor = workflow in ('create', 'calculator')
    strategy_open = '<section class="tw-strategy-detail" aria-label="Team strategy">'
    strategy_close = '</section>'
    market_panel = '<section id="trade-balance" class="ti-market-balance" aria-live="polite" tabindex="-1"></section>'
    balance_controls = '<section id="trade-balancing" aria-label="Options to balance this trade"><h3>Options to balance this trade</h3><button id="trade-balance-offer" type="button" disabled aria-describedby="calculator-balance-status">Balance offer · preview options</button><p id="calculator-balance-status" class="tw-balance-status" role="status" aria-live="polite" aria-atomic="true"></p></section>'
    calculator_panel = (f'<section class="tw-calculator" aria-label="Market calculator">{market_panel}{balance_controls}<div class="ti-actions"><button id="calculator-protect" type="button">Protect assets</button></div><div class="tw-packages"><section><h4>Side A · You send</h4><div id="calculator-sent"></div></section><section><h4>Side B · You receive</h4><div id="calculator-received"></div></section></div><p class="muted">Use the searchable owned-asset lists to add players and exact picks. Market totals update immediately.</p></section>' if market_editor else '')
    market_detail = '' if market_editor else f'<details class="tw-market-detail"><summary>Market Balance · acquisition-price evidence</summary>{market_panel}</details>'
    calculator_link = '' if calculator else f'<a class="ti-action" href="/trades/calculator?front_office={active}">Open this workspace in Calculator</a>'
    protect_control = '<button id="calculator-lock" type="button">Do not trade selected exact asset</button>' if market_editor else ''
    recommended_controls = '''<label for="recommendation-filter">Opportunity filter</label><select id="recommendation-filter" disabled><option value="all">All supported opportunities</option><option value="win_now">Win Now</option><option value="value">Value</option><option value="roster_fit">Roster Fit</option><option value="future">Draft Capital</option><option value="sell_high" disabled>Sell High — movement evidence unavailable</option></select><p class="muted">Filters select supported opportunity types; they do not change your strategy or valuations.</p>''' if workflow == 'recommended' else ''
    shop_controls = '''<details id="shop-refinements"><summary>Refine Shop results · optional</summary><section aria-label="Shop search preferences"><label for="shop-preference">Search preference (this session only)</label>
<select id="shop-preference"><option value="best_overall">Best Overall Return</option><option value="win_now">Win-Now Help</option><option value="youth_rebuild">Youth / Rebuild</option><option value="draft_capital">Draft Capital</option><option value="position_need">Position Need</option><option value="custom">Custom — protect assets</option></select>
<label for="shop-position">Position for Position Need</label><select id="shop-position" disabled><option value="QB">QB</option><option value="RB">RB</option><option value="WR">WR</option><option value="TE">TE</option></select>
<label for="shop-protected">Keep these assets out of outgoing packages</label><select id="shop-protected" multiple aria-label="Protected outgoing assets"></select>
<p class="muted">Preferences order supported returns; they do not change the trade assessment. Age is not a longevity forecast. Custom uses the protected assets selected here.</p></section></details>''' if workflow == 'shop' else ''
    partner_placeholder = 'All eligible teams' if workflow == 'shop' else 'Choose a trade partner'
    partner_help = '<p id="shop-partner-help" class="muted">Choosing a partner is optional. With All eligible teams, Shop searches eligible counterparties while keeping your outgoing asset.</p>' if workflow == 'shop' else ''
    heading = f'<div class="tw-heading"><h2>{escape(title)}</h2></div>'
    discovery = ('<button id="trade-find" class="tw-primary-action" type="button" disabled>Generate Trades</button>' if workflow == 'recommended' else '<button id="trade-find" class="tw-primary-action" type="button" disabled>Find Bilateral Options</button>' if workflow in ('shop', 'trade-for') else '')
    partner_controls = f'<div class="tw-partner-controls"><label for="trade-partner">Counterparty</label><select id="trade-partner"><option value="">{partner_placeholder}</option></select>{partner_help}</div>'
    strategy_controls = f'{strategy_open}<label class="tw-control-label" for="trade-strategy">Trade strategy <small class="tw-intent-help" id="trade-strategy-help">Not your saved goal</small></label><select id="trade-strategy" aria-label="Trade strategy" aria-describedby="trade-strategy-help" disabled><option value="">No goal</option><option value="WIN NOW">Win Now</option><option value="RETOOL">Retool</option><option value="REBUILD">Rebuild</option></select>{strategy_close}'
    is_discovery = workflow in ('recommended', 'shop', 'trade-for')
    pick_options = '<label class="tw-check"><input id="trade-include-picks" type="checkbox" checked disabled>Include draft picks in this search</label><p class="muted">Turning picks off excludes exact current picks from generated packages only. It does not change your entered offer or saved preferences.</p>'
    optional_search = (shop_controls.replace('</details>', pick_options + '</details>') if workflow == 'shop' else f'<details id="trade-search-options"><summary>Search options · optional</summary>{recommended_controls}{pick_options}</details>') if is_discovery else ''
    intent_nav = f'<nav class="tw-intent-nav" aria-label="Trade purpose"><a href="/trades/recommended?front_office={active}" {"aria-current=page" if is_discovery else ""}>Generate Trades</a><a href="/trades/calculator?front_office={active}" {"aria-current=page" if not is_discovery else ""}>Evaluate Trade</a></nav>'
    primary = discovery if is_discovery else f'<button id="trade-run" class="tw-primary-action" type="button" disabled>{"Advanced DTOS analysis" if calculator else "Evaluate Trade"}</button>'
    next_ideas = '<button id="recommendation-refresh" type="button" disabled hidden aria-describedby="recommendation-status">Show Next 5</button>' if workflow == 'recommended' else ''
    tray = '<div id="trade-tray" class="tw-tray" hidden><span id="trade-tray-text"></span><button id="trade-tray-view" type="button">View Trade</button></div>'
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
<section id="trade-builder" class="card tw-workspace" data-trade-workflow="{workflow}" data-front-office="{active}" data-league="{escape(league, quote=True)}" data-preload-asset="{escape(str(asset_id or ''), quote=True)}" data-owner-roster="{int(owner_roster_id or 0)}">
{heading}
{intent_nav}
<p id="trade-context" class="muted">Loading current league assets…</p>
<div id="trade-intent-controls" class="tw-intent-controls">{strategy_controls}</div>
{optional_search}
<section id="trade-target" class="tw-target" hidden aria-label="Selected trade target"></section>
<div class="tw-primary-actions">{primary}{next_ideas}</div>
<p id="recommendation-status" class="ds-inline-feedback" role="status" aria-live="off" aria-atomic="true">Preparing current league assets…</p>
<button id="trade-cancel" type="button" hidden>Cancel current operation</button>
<span id="trade-results-home"></span><section id="trade-result" role="status" aria-live="polite" tabindex="-1" hidden></section>
{tray}
{'<details id="trade-asset-options"><summary>Owned assets and exact constraints · optional</summary>' if workflow == 'recommended' else ''}
{partner_controls}
<div id="trade-board"><div class="tw-side-tabs" role="group" aria-label="Asset side"><button type="button" data-side="sent" aria-pressed="true">My assets</button><button type="button" data-side="received" aria-pressed="false">Their assets</button></div>
<div class="tw-boards"><section id="trade-sent-board"></section><section id="trade-received-board"></section></div></div>
{'</details>' if workflow == 'recommended' else ''}
<div id="trade-workspace-tools"><a href="/trades?front_office={active}" aria-label="All Trade Workflows">All workflows</a><button id="trade-start-new" type="button">Start New Trade</button><button id="trade-clear-package" type="button" hidden>Clear package · keep objective and protections</button></div>
{calculator_panel}
<section id="trade-review" tabindex="-1" hidden><h3>Your proposal</h3><div class="tw-packages"><section><h4>You send</h4><div id="trade-sent-chips"></div></section><section><h4>You receive</h4><div id="trade-received-chips"></div></section></div></section>
<div class="ti-actions"><button id="trade-view" type="button">View Trade</button>{'' if market_editor else '<button id="trade-run" type="button">Evaluate Trade</button>'}<button id="trade-edit" type="button">Edit Trade</button><button id="trade-adjust" type="button">Adjust Offer / protect assets</button>{'' if workflow in ('recommended', 'shop', 'trade-for') else '<button id="trade-find" type="button" hidden>Find Bilateral Options</button>'}{calculator_link}</div>
<section id="trade-assist" class="tw-protection-controls" hidden><label for="trade-instruction">How should DTOS adjust it?</label><input id="trade-instruction" maxlength="300" placeholder="Make it cheaper, or name an asset to protect"><label for="trade-constraint-asset">Exact asset to keep or replace</label><select id="trade-constraint-asset"><option value="">Choose a specific owned asset</option></select>{protect_control}<button id="trade-release-lock" type="button">Remove selected adjustment lock</button><p>Keep and replace controls apply to this exact identity. Alternatives are previews; your proposal changes only when you adopt one.</p><details><summary>More adjustment options</summary><div class="ti-actions">{adjustments}</div></details><button id="trade-apply-adjust" type="button">Preview revised offers</button><button id="trade-alternatives" type="button">Preview alternatives</button></section>
<button id="trade-build-own" type="button" {'hidden' if workflow == 'create' else ''}>Build My Own</button>
{market_detail}{balance_controls if not market_editor else ""}
<details id="trade-source-context"><summary>League identity details</summary><p id="trade-source-context-identity"></p></details>
<p class="muted">Ownership is revalidated before evaluation. Market Balance is neutral market evidence, not the recommendation. DTOS evaluates proposals; it does not send trades to Sleeper.</p></section><p id="trade-operation-announcement" class="tw-announcement" role="status" aria-live="polite" aria-atomic="true"></p><script src="/static/js/strategy_session.js" defer></script><script src="/static/js/trade_workspace.js" defer></script>'''
