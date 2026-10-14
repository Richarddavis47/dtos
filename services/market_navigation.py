"""Bounded, league-scoped Market return links. No retained navigation history."""
from urllib.parse import parse_qsl, urlencode, urlsplit


def market_return(origin, source_league, selected_league):
    if not origin or str(source_league or "") != str(selected_league or "") or len(origin) > 1600:
        return None
    parsed = urlsplit(origin)
    if parsed.scheme or parsed.netloc or parsed.path != "/market" or parsed.fragment:
        return None
    allowed = {"q", "position", "availability", "sort", "direction", "front_office", "selected", "offset", "limit"}
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key not in allowed for key, _ in pairs) or len({k for k, _ in pairs}) != len(pairs):
        return None
    values = dict(pairs)
    if len(values.get("q", "")) > 200 or len(values.get("selected", "")) > 200:
        return None
    for key in ("offset", "limit", "front_office"):
        if key in values and (not values[key].isdecimal() or int(values[key]) > 1000000):
            return None
    return "/market" + ("?" + urlencode(pairs) if pairs else "")
