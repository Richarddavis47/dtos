from src.core.market_intelligence.providers.base import FieldMarketProvider


class SleeperAdpProvider(FieldMarketProvider):
    name = "Sleeper ADP"
    field = "sleeper_adp_value"
    aliases = ("adp_value",)
