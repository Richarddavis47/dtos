"""Shared standard-library structural reader for trusted test HTML.

Moved unchanged from the customer Trade controls; no browser, provider,
application preparation or optional dependency is imported by this helper.
"""
from html.parser import HTMLParser


class _Document(HTMLParser):
    """Small structural reader for trusted rendered HTML, with no dependency."""
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = dict(tag='root', attrs={}, children=[])
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = dict(tag=tag, attrs=dict(attrs), children=[])
        self.stack[-1]['children'].append(element)
        if tag not in {'br', 'img', 'input', 'link', 'meta', 'hr', 'source', 'wbr'}:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]['tag'] == tag:
                self.stack = self.stack[:index]
                return

    def handle_data(self, value):
        self.stack[-1]['children'].append(value)


def _elements(element, *, direct=False):
    for child in element['children']:
        if isinstance(child, dict):
            yield child
            if not direct:
                yield from _elements(child)


def _class(element, name, *, direct=False):
    return next((child for child in _elements(element, direct=direct)
                 if name in (child['attrs'].get('class') or '').split()), None)


def _text(element):
    return ''.join(_text(child) if isinstance(child, dict) else child
                   for child in element['children'])


