from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.game.core import (
    GameDeal,
    COMMON_GAME_SOURCE_NAMES,
    HistoricalPriceData,
    LowestPriceInPeriod,
    ProductType,
)
from steaminlinebot.game.protondb_report import ProtonDBReport
from steaminlinebot.integration.protondb_client import ScrapedProtonDBReport


class IGameRepository(ABC):
    @abstractmethod
    def add_game_source(
        self, game_id: int, game_source: COMMON_GAME_SOURCE_NAMES, external_id: str
    ) -> None: ...

    @abstractmethod
    def get_game_id_on_source(
        self, game_id: int, game_source: COMMON_GAME_SOURCE_NAMES
    ) -> Optional[str]: ...

    @abstractmethod
    def get_or_insert_game(
        self,
        title: str | None,
        product_type: ProductType,
        source: str,
        external_id: str,
    ) -> int: ...

    @abstractmethod
    def insert_deal(self, game_id: int, deal: GameDeal) -> int: ...

    @abstractmethod
    def get_historical_price(
        self, game_id: int, country_2l: str, scope: LowestPriceInPeriod
    ) -> HistoricalPriceData | None: ...

    @abstractmethod
    def insert_proton_report(
        self, game_id: int, report: ScrapedProtonDBReport | None
    ) -> ProtonDBReport | None: ...

    @abstractmethod
    def upsert_historical_price(
        self, game_id: int, historical_price: HistoricalPriceData
    ) -> None: ...

    @abstractmethod
    def record_observation(
        self,
        title: str | None,
        product_type: ProductType,
        source: str,
        external_id: str,
        deals: list[GameDeal],
        historical_price: HistoricalPriceData | None,
        proton_report: ScrapedProtonDBReport | None,
    ) -> tuple[int, ProtonDBReport | None]: ...
