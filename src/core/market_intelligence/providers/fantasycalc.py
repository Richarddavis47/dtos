from src.core.market_intelligence.providers.base import FieldMarketProvider


class FantasyCalcProvider(FieldMarketProvider):
    name = "FantasyCalc"
    field = "fantasycalc_value"
