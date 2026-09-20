"""Unadjusted canonical acquisition prices, never strategic/package utility."""
from decimal import Decimal
from math import isfinite


def package_market(assets):
    known, missing = [], []
    for asset in assets:
        price = asset.trade_value
        if price is None:
            missing.append(asset.asset_id)
            continue
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not isfinite(price) or price < 0:
            raise ValueError('Canonical Market price must be finite and nonnegative')
        known.append(Decimal(str(price)))
    subtotal = float(sum(known, Decimal(0))) if known else None
    return {'availability': 'partial' if known and missing else 'unavailable' if missing else 'full',
            'total': None if missing else float(sum(known, Decimal(0))),
            'known_subtotal': subtotal, 'priced_assets': len(known),
            'missing_asset_ids': missing, 'asset_count': len(assets)}


def market_balance(sent, received):
    left, right = package_market(sent), package_market(received)
    full = left['availability'] == right['availability'] == 'full'
    known = left['priced_assets'] + right['priced_assets']
    return {'availability': 'full' if full else 'partial' if known else 'unavailable',
            'sent': left, 'received': right,
            'difference': float(Decimal(str(right['total'])) - Decimal(str(left['total']))) if full else None,
            'ratio': right['total'] / left['total'] if full and left['total'] > 0 else None,
            'unit': 'canonical_acquisition_market_price', 'package_adjustments': False}
