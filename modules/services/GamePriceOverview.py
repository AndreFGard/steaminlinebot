from dataclasses import dataclass
from sqlite3 import Connection

from modules.async_lru_cache_ttl import async_lru_cache_ttl
from modules.services.GGDealsClient import GGDealsAPI
from modules.services.Money import Money


@dataclass
class PriceOverviewVM:
    best_price: Money
    bestKeyShopPrice: Money
    bestHistoricalRetail: Money
    bestHistoricalKeyShop: Money
    country: str


class GamePriceOverview:
    def __init__(self, db: Connection):
        self._db = db

    @async_lru_cache_ttl
    async def _try_cached_price_overview(self, appid) -> PriceOverviewVM | None:
        """Not implemented yet"""
        return None

    async def get_games_price_overview(
        self, appids: list[str]
    ) -> list[PriceOverviewVM]: ...
