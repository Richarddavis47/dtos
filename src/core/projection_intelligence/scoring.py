"""League-specific conversion of projected football statistics."""
from __future__ import annotations

from typing import Any
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP


SCORING_METHOD_VERSION = "sleeper-coefficient-4dp-decimal-v1"
DISPLAY_METHOD_VERSION = "sleeper-web-sequential-number-tofixed2-v1"


def scoring_coefficient(value: Any) -> Decimal:
    """Sleeper calcFn normalizes weights with Math.round(weight * 10000).

    Use exact decimals and JS's ties-toward-positive-infinity rule. This is
    coefficient normalization, NOT projection/stat rounding. Preserve source
    coefficients in provenance; do not rewrite league settings.
    """
    scaled = Decimal(str(value or 0)) * 10000
    return (scaled + Decimal('.5')).to_integral_value(rounding=ROUND_FLOOR) / 10000


STAT_KEYS = {
    "pass_yd": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
    "pass_2pt": "pass_2pt", "rush_yd": "rush_yd", "rush_td": "rush_td",
    "rush_2pt": "rush_2pt", "rec": "rec", "rec_yd": "rec_yd",
    "rec_td": "rec_td", "rec_2pt": "rec_2pt", "fum_lost": "fum_lost",
    "fgm": "fgm", "fgmiss": "fgmiss", "xpm": "xpm", "xpmiss": "xpmiss",
}
STAT_KEYS.update({key: key for key in (
    'pass_att', 'pass_cmp', 'pass_inc', 'pass_cmp_40p', 'pass_fd', 'pass_sack',
    'pass_td_40p', 'pass_td_50p', 'pass_int_td', 'rush_att', 'rush_fd', 'rush_40p',
    'rush_td_40p', 'rush_td_50p', 'rec_fd', 'rec_40p', 'rec_td_40p', 'rec_td_50p',
    'rec_0_4', 'rec_5_9', 'rec_10_19', 'rec_20_29', 'rec_30_39', 'fum',
    'bonus_rec_te', 'bonus_rec_rb', 'bonus_rec_wr', 'bonus_rush_td_qb',
    'bonus_pass_yd_300', 'bonus_pass_yd_400', 'bonus_rush_yd_100', 'bonus_rec_yd_100',
    'fgm_0_19', 'fgm_20_29', 'fgm_30_39', 'fgm_40_49', 'fgm_50p',
)})


def fantasy_points(stats: dict[str, Any], scoring: dict[str, Any], position: str = "") -> float:
    """Score raw projected stats with the league's actual supported rules."""
    total = Decimal(0)
    for stat, scoring_key in STAT_KEYS.items():
        total += Decimal(str(stats.get(stat) or 0)) * scoring_coefficient(scoring.get(scoring_key))
    if position.upper() == "TE" and 'bonus_rec_te' not in stats:
        total += Decimal(str(stats.get('rec') or 0)) * scoring_coefficient(
            scoring.get('bonus_rec_te', scoring.get('rec_te')))
    # A projected mean crossing a yardage threshold is not evidence that the
    # bonus will be earned. Only an explicit source bonus statistic is scored.
    return float(total)


def sleeper_web_display(stats: dict[str, Any], scoring: dict[str, Any],
                        source_stat_order: list[str] | None) -> str | None:
    """Replay only the proven web display rule, never an optimization input.

    Public Sleeper code iterates Object.keys(stats), adds binary64 calcFn
    contributions sequentially, and calls Number.toFixed(2). Canonical decimal
    totals deliberately do not inherit those binary rounding artifacts.
    Older evidence without source order cannot prove exact web display parity.
    """
    if (source_stat_order is None or len(source_stat_order) != len(set(source_stat_order))
            or set(source_stat_order) != set(stats)
            or not any(key in STAT_KEYS for key in stats)):
        return None
    total = 0.0
    for key in source_stat_order:
        if key in STAT_KEYS:
            total += float(scoring_coefficient(scoring.get(STAT_KEYS[key]))) * float(stats[key])
    # ECMA toFixed chooses the nearest decimal to the exact binary value, with
    # ties away from zero. Decimal(str(total)) would erase the binary boundary.
    return format(Decimal.from_float(total).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f')
