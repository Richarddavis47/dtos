"""Escaped compact presentation over selected prepared facts."""
from html import escape

from src.ui.home_trade_opportunities import cards as offer_cards


def cards(items):
    output = []
    for item in items:
        if item['family'] == 'offer':
            # Retain the existing exact You Send/Receive, verdict and offer URL.
            row = dict(item['offer'])
            row['evaluation'] = {**row['evaluation'], 'why_you_would_do_it': item['reason'],
                                 'major_drawback': item['drawback']}
            output.append(offer_cards([row], item['roster_id']))
            continue
        details = ''.join('<p>' + escape(str(line)) + '</p>' for line in item['details'] if line)
        label = 'Evidence limit' if item['family'] == 'attention' else 'Keep in mind'
        output.append(f'''<article class="home-brief-insight" data-brief-family="{escape(item['family'])}"><h3>{escape(item['title'])}</h3><p><b>Why:</b> {escape(item['reason'])}</p><p><b>{label}:</b> {escape(item['drawback'])}</p><a class="ds-action" href="{escape(item['href'], quote=True)}">{escape(item['action'])} →</a>''' +
                      (f'<details><summary>Supporting evidence</summary>{details}</details>' if details else '') + '</article>')
    return ''.join(output[:2]) + ('<details class="ds-home-detail" id="home-brief-more"><summary>More Front Office insights</summary>' + ''.join(output[2:]) + '</details>' if len(output) > 2 else '')


CSS = '''.home-brief-insight{border:1px solid #35413b;border-radius:12px;padding:14px;margin:10px 0;overflow-wrap:anywhere}.home-brief-insight h3,.home-brief-insight p{margin:6px 0}.home-brief-insight .ds-action,#home-opportunities summary{min-height:44px;display:flex;align-items:center}#home-opportunities summary{cursor:pointer}#home-opportunities a:focus-visible,#home-opportunities summary:focus-visible,#home-opportunities button:focus-visible{outline:2px solid var(--green,#67d995);outline-offset:3px}'''
