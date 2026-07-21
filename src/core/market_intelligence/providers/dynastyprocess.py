from src.core.market_intelligence.providers.base import FieldMarketProvider


class DynastyProcessProvider(FieldMarketProvider):
    name = "DynastyProcess"
    field = "dynastyprocess_value"
