from modules.services.GGDealsClient import GGDealsAPI
from dataclasses import dataclass
from modules.services.Money import Money
from sqlite3 import Connection
from modules.async_lru_cache_ttl import async_lru_cache_ttl


@dataclass
class PriceOverviewVM:
    bestPrice: Money
    bestKeyShopPrice: Money
    bestHistoricalRetail: Money
    bestHistoricalKeyShop: Money
    country: str


class GamePriceOverview:
    def __init__(self, db: Connection):
        self._db = db

    @async_lru_cache_ttl
    async def _tryCachedPriceOverview(self, appid) -> PriceOverviewVM | None:
        """Not implemented yet"""
        return None

    async def getGamesPriceOverview(
        self, appids: list[str]
    ) -> list[PriceOverviewVM]: ...
