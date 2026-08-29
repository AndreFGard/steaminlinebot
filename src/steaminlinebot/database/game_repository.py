import datetime
import logging
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy import Connection, Engine, Row, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from steaminlinebot.database.schema import (
    cost_table,
    game_external_id_table,
    game_source_table,
    game_table,
    historical_low_table,
    proton_report_table,
    DBProductType,
    DealFlag_,
    LowestPriceInPeriod_,
)
from steaminlinebot.game.core import (
    GameDeal,
    Game,
    GameSource,
    HistoricalPriceData,
    ProductType,
    SourcedGame,
)
from steaminlinebot.game.protondb_report import ProtonDBReport, ProtonDBTier
from steaminlinebot.integration.protondb_client import ScrapedProtonDBReport

log = logging.getLogger(__name__)


class SourceNotFoundError(LookupError):
    """Raised when a named game source is not found in game_source."""


class IGameRepository(ABC):
    @abstractmethod
    def add_game_source(
        self, game_id: int, game_source: GameSource, external_id: str
    ) -> None: ...

    @abstractmethod
    def get_game_id_on_source(
        self, game_id: int, game_source: GameSource
    ) -> Optional[str]: ...

    @abstractmethod
    def insert_game(
        self,
        title: str,
        product_type: ProductType,
        source: GameSource,
        external_id: str,
    ) -> int: ...

    @abstractmethod
    def insert_full_game(
        self,
        title: str,
        product_type: ProductType,
        external_id: str,
        url: str,
        deals: list[GameDeal],
        game_source: GameSource,
        price_overview: Optional[HistoricalPriceData],
        proton_db_report: Optional[ScrapedProtonDBReport] = None,
    ) -> SourcedGame:
        """Returns the id on the specified index"""
        ...


class GameRepository(IGameRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def add_game_source(
        self, game_id: int, game_source: GameSource, external_id: str
    ) -> None:
        with self._engine.begin() as conn:
            source = _get_source_by_name(conn, game_source.value)
            conn.execute(
                sqlite_insert(game_external_id_table)
                .values(
                    game_id=game_id,
                    external_id=external_id,
                    source_id=source.id,
                )
                .on_conflict_do_update(
                    index_elements=["game_id", "source_id"],
                    set_={"external_id": external_id},
                )
            )

    def get_game_id_on_source(
        self, game_id: int, game_source: GameSource
    ) -> Optional[str]:
        with self._engine.begin() as conn:
            source = _get_source_by_name(conn, game_source.value)
            row = conn.execute(
                select(game_external_id_table).where(
                    game_external_id_table.c.game_id == game_id,
                    game_external_id_table.c.source_id == source.id,
                )
            ).first()
            if row is not None:
                return row.external_id
            return None

    def insert_game(
        self,
        title: str,
        product_type: ProductType,
        source: GameSource,
        external_id: str,
    ) -> int:
        with self._engine.begin() as conn:
            source_row = _get_source_by_name(conn, source.value)
            return _get_or_insert_game(
                conn, title, product_type, source_row.id, external_id
            )

    def insert_full_game(
        self,
        title: str,
        product_type: ProductType,
        external_id: str,
        url: str,
        deals: list[GameDeal],
        game_source: GameSource,
        price_overview: Optional[HistoricalPriceData],
        proton_db_report: Optional[ScrapedProtonDBReport] = None,
    ) -> SourcedGame:
        with self._engine.begin() as conn:
            source = _get_source_by_name(conn, game_source.value)
            game_id = _get_or_insert_game(
                conn, title, product_type, source.id, external_id
            )
            game = Game(id=game_id, title=title, product_type=product_type)

            inserted_deals = [
                _insert_deal(conn, game_id, source.id, deal, url) for deal in deals
            ]

            if price_overview is not None:
                _insert_historical_low(conn, game_id, price_overview)

            proton_db_info = _insert_proton_report(conn, game_id, proton_db_report)

            return SourcedGame(
                game=game,
                external_id=external_id,
                game_source=game_source,
                deals=inserted_deals,
                url=url,
                price_overview=price_overview,
                proton_db_info=proton_db_info,
            )


def _get_source_by_name(conn: Connection, name: str) -> Row:
    """This errors if the source is not there."""
    row = conn.execute(
        select(game_source_table).where(game_source_table.c.name == name)
    ).first()

    if row is None:
        raise SourceNotFoundError(
            f"Game source '{name}' not found in game_source table."
        )

    return row


def _get_or_insert_game(
    conn: Connection,
    title: str,
    product_type: ProductType,
    source_id: int,
    external_id: str,
) -> int:
    """Return existing game_id, or insert a new game + external-id row."""
    existing = conn.execute(
        select(game_external_id_table.c.game_id).where(
            game_external_id_table.c.source_id == source_id,
            game_external_id_table.c.external_id == external_id,
        )
    ).first()

    if existing is not None:
        return existing.game_id

    result = conn.execute(
        game_table.insert().values(
            title=title,
            product_type=DBProductType(product_type.value),
        )
    )
    game_id: int = result.inserted_primary_key[0]  # type: ignore[assignment]

    conn.execute(
        sqlite_insert(game_external_id_table)
        .values(game_id=game_id, source_id=source_id, external_id=external_id)
        .on_conflict_do_nothing(index_elements=["source_id", "external_id"])
    )

    return game_id


def _insert_deal(
    conn: Connection,
    game_id: int,
    source_id: int,
    deal: GameDeal,
    url: str,
) -> GameDeal:
    now = datetime.datetime.now(datetime.timezone.utc)
    flag = (
        DealFlag_(deal.historical_deal.value)
        if deal.historical_deal is not None
        else None
    )

    result = conn.execute(
        cost_table.insert().values(
            game_id=game_id,
            source_id=source_id,
            country_alpha2=deal.country_l2,
            currency=deal.currency_3l,
            collected_date=deal.observed_date,
            insertion_date=now,
            value_minor=deal.value_minor,
            full_value_minor=deal.full_value_minor,
            discount=deal.discount,
            flag=flag,
            price_expires_at=deal.price_expires_at,
            url=url,
        )
    )
    result.inserted_primary_key[0]  # type: ignore[assignment]

    return GameDeal(
        value_minor=deal.value_minor,
        currency_3l=deal.currency_3l,
        full_value_minor=deal.full_value_minor,
        discount=deal.discount,
        country_l2=deal.country_l2,
        price_expires_at=deal.price_expires_at,
        observed_date=deal.observed_date,
        historical_deal=deal.historical_deal,
    )


def _insert_historical_low(
    conn: Connection, game_id: int, price_overview: HistoricalPriceData
) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    conn.execute(
        historical_low_table.insert().values(
            game_id=game_id,
            country_alpha2=price_overview.country_l2,
            scope=LowestPriceInPeriod_(price_overview.scope.value),
            currency=price_overview.currency_3l,
            lowest_value_minor=price_overview.lowest_value_minor,
            collected_date=now,
        )
    )


def _insert_proton_report(
    conn: Connection,
    game_id: int,
    report: ScrapedProtonDBReport | None,
) -> ProtonDBReport | None:
    if report is None:
        return None

    conn.execute(
        proton_report_table.insert().values(
            game_id=game_id,
            source_id=None,
            best_reported_tier=report.best_reported_tier,
            confidence=report.confidence,
            score=report.score,
            tier=report.tier,
            total=report.total,
            trending_tier=report.trending_tier,
            collected_date=datetime.datetime.now(datetime.timezone.utc),
        )
    )

    return ProtonDBReport(
        game_id=game_id,
        best_reported_tier=ProtonDBTier(report.best_reported_tier),
        confidence=report.confidence,
        score=report.score,
        tier=ProtonDBTier(report.tier),
        total=report.total,
        trending_tier=ProtonDBTier(report.trending_tier),
    )
