"""Bounded, league-scoped Market return links. No retained navigation history."""
from urllib.parse import parse_qsl, urlencode, urlsplit


def market_return(origin, source_league, selected_league):
    if not origin or str(source_league or "") != str(selected_league or "") or len(origin) > 1600:
        return None
    if any(ord(char) < 32 for char in origin):
        return None
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc or parsed.path != "/market" or parsed.fragment:
        return None
    allowed = {"q", "position", "availability", "sort", "direction", "front_office", "selected", "offset", "limit"}
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key not in allowed for key, _ in pairs) or len({k for k, _ in pairs}) != len(pairs):
        return None
    values = dict(pairs)
    for key, supported in {
        "position": {"", "QB", "RB", "WR", "TE", "PICK"},
        "availability": {"", "rostered", "day_traders_free_agent", "taxi", "retired", "owned_pick"},
        "sort": {"market", "intrinsic", "contender", "rebuilder", "confidence", "risk", "liquidity"},
        "direction": {"asc", "desc"},
    }.items():
        if key in values and values[key] not in supported:
            return None
    if len(values.get("q", "")) > 200 or len(values.get("selected", "")) > 200:
        return None
    for key in ("offset", "limit", "front_office"):
        if key in values and (not values[key].isdecimal() or int(values[key]) > 1000000):
            return None
    if "limit" in values and not 10 <= int(values["limit"]) <= 100:
        return None
    if "front_office" in values and int(values["front_office"]) < 1:
        return None
    return "/market" + ("?" + urlencode(pairs) if pairs else "")
