import datetime
import logging
import traceback
from typing import Optional

from sqlalchemy import Connection, Engine, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from steaminlinebot.database.schema import (
    cost_table,
    game_external_id_table,
    game_source_table,
    game_table,
    historical_low_table,
    proton_report_table,
)
from steaminlinebot.game.core import (
    GameDeal,
    COMMON_GAME_SOURCE_NAMES,
    HistoricalPriceData,
    LowestPriceInPeriod,
    ProductType,
)
from steaminlinebot.game.protondb_report import ProtonDBReport, ProtonDBTier
from steaminlinebot.game.repository import IGameRepository
from steaminlinebot.integration.protondb_client import ScrapedProtonDBReport

log = logging.getLogger(__name__)


class SourceNotFoundError(LookupError):
    """Raised when a named game source is not found in game_source."""


class GameRepository(IGameRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def add_game_source(
        self, game_id: int, game_source: COMMON_GAME_SOURCE_NAMES, external_id: str
    ) -> None:
        with self._engine.begin() as conn:
            source = _get_source_by_name(conn, game_source.value)
            conn.execute(
                sqlite_insert(game_external_id_table)
                .values(game_id=game_id, external_id=external_id, source_id=source)
                .on_conflict_do_update(
                    index_elements=["game_id", "source_id"],
                    set_={"external_id": external_id},
                )
            )

    def get_historical_price(
        self, game_id: int, country_2l: str, scope: LowestPriceInPeriod
    ) -> HistoricalPriceData | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(historical_low_table).where(
                    historical_low_table.c.game_id == game_id,
                    historical_low_table.c.country_alpha2l == country_2l,
                    historical_low_table.c.scope == scope.value,
                )
            ).first()
            if row is not None:
                return HistoricalPriceData(
                    scope=LowestPriceInPeriod(row.scope),
                    lowest_value_minor=row.lowest_value_minor,
                    country_l2=row.country_alpha2l,
                    currency_3l=row.currency,
                )
            return None

    def insert_proton_report(
        self, game_id: int, report: ScrapedProtonDBReport | None
    ) -> ProtonDBReport | None:
        with self._engine.begin() as conn:
            return _insert_proton_report(conn, game_id, report)

    def upsert_historical_price(
        self, game_id: int, historical_price: HistoricalPriceData
    ) -> None:
        with self._engine.begin() as conn:
            _upsert_historical_low(conn, game_id, historical_price)

    def get_game_id_on_source(
        self, game_id: int, game_source: COMMON_GAME_SOURCE_NAMES
    ) -> Optional[str]:
        with self._engine.begin() as conn:
            source = _get_source_by_name(conn, game_source.value)
            row = conn.execute(
                select(game_external_id_table).where(
                    game_external_id_table.c.game_id == game_id,
                    game_external_id_table.c.source_id == source,
                )
            ).first()
            if row is not None:
                return row.external_id
            return None

    def get_or_insert_game(
        self,
        title: str | None,
        product_type: ProductType,
        source: str,
        external_id: str,
    ) -> int:
        with self._engine.begin() as conn:
            source_row = _get_source_by_name(conn, source)
            return _get_or_insert_game(
                conn, title or "", product_type, source_row, external_id
            )

    def insert_deal(self, game_id: int, deal: GameDeal) -> int:
        with self._engine.begin() as conn:
            source_id = _get_source_by_name(conn, deal.source_shop)
            return _insert_deal(conn, game_id, source_id, deal)

    def record_observation(
        self,
        title: str | None,
        product_type: ProductType,
        source: str,
        external_id: str,
        deals: list[GameDeal],
        historical_price: HistoricalPriceData | None,
        proton_report: ScrapedProtonDBReport | None,
    ) -> tuple[int, ProtonDBReport | None]:
        game_id = self.get_or_insert_game(title, product_type, source, external_id)

        for deal in deals:
            if deal is not None:
                try:
                    self.insert_deal(game_id, deal)
                except Exception:
                    log.error(
                        f"Failed to insert deal '{deal.model_dump_json(indent=2)}'"
                    )
                    traceback.print_exc()

        proton_db_info = self.insert_proton_report(game_id, proton_report)

        if historical_price is not None:
            self.upsert_historical_price(game_id, historical_price)

        return game_id, proton_db_info


def _get_source_by_name(conn: Connection, name: str) -> int:
    row = conn.execute(
        select(game_source_table).where(game_source_table.c.name == name)
    ).first()

    if row is None:
        raise SourceNotFoundError(
            f"Game source '{name}' not found in game_source table."
        )
    return row.id


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
            product_type=ProductType(product_type.value),
        )
    )
    assert result.inserted_primary_key is not None

    game_id = result.inserted_primary_key[0]
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
) -> int:
    now = datetime.datetime.now(datetime.timezone.utc)
    flag = (
        LowestPriceInPeriod(deal.historical_deal.value)
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
            url=deal.url,
        )
    )
    assert result.inserted_primary_key is not None
    return result.inserted_primary_key[0]


def _upsert_historical_low(
    conn: Connection, game_id: int, price_overview: HistoricalPriceData
) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    values = dict(
        game_id=game_id,
        country_alpha2=price_overview.country_l2,
        scope=LowestPriceInPeriod(price_overview.scope.value),
        currency=price_overview.currency_3l,
        lowest_value_minor=price_overview.lowest_value_minor,
        collected_date=now,
    )
    conn.execute(
        sqlite_insert(historical_low_table)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["game_id", "country_alpha2", "scope"],
            set_=values,
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
