from src.core.market_intelligence.providers.base import FieldMarketProvider


class KeepTradeCutProvider(FieldMarketProvider):
    name = "KeepTradeCut"
    field = "keeptradecut_value"
    aliases = ("ktc_value",)
