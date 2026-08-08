import datetime
import logging
from abc import ABC, abstractmethod

from sqlalchemy import Connection, Engine, Row, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from steaminlinebot.database.schema import (
    cost_table,
    game_external_id_table,
    game_source_table,
    game_table,
    proton_report_table,
    ProductType_,
)
from steaminlinebot.game.GameResultV2 import (
    CostData,
    GameResultV2,
    GameSourceInfo,
    ScrapedSteamGame,
)
from steaminlinebot.game.ProtonDBReportV2 import ProtonDBReportV2, ProtonDBTier
from steaminlinebot.integration.ProtonDBClient import ScrapedProtonDBReport

log = logging.getLogger(__name__)


class SourceNotFoundError(LookupError):
    """Raised when a named game source is not found in game_source."""


class IGameResultRepositoryV2(ABC):
    """Persists scraped game data and returns a fully-hydrated GameResultV2.

    Args:
        game: The scraped game to persist.
        source_name: Name of the store source (e.g. ``"Steam"``). Must exist
            in the ``game_source`` table.

    Returns:
        GameResultV2 with all database-generated IDs populated.

    Raises:
        SourceNotFoundError: If *source_name* is not found in ``game_source``.
    """

    @abstractmethod
    def insert_game_result(
        self, game: ScrapedSteamGame, source_name: str
    ) -> GameResultV2: ...


class GameResultRepositoryV2(IGameResultRepositoryV2):
    def __init__(self, engine: Engine):
        self._engine = engine

    def insert_game_result(
        self, game: ScrapedSteamGame, source_name: str
    ) -> GameResultV2:
        with self._engine.begin() as conn:
            source = _get_source(conn, source_name)
            game_id = _get_or_insert_game(conn, game, source.id, game.appid)
            cost_data = _insert_cost(conn, game_id, source.id, game)
            proton_db_info = _insert_proton_report(conn, game_id, game.proton_db_report)

            return GameResultV2(
                id=game_id,
                title=game.title,
                product_type=game.product_type,
                cost=cost_data,
                url=game.link,
                game_source=GameSourceInfo(
                    source_name=source.name,
                    external_id=game.appid,
                    itad_shop_id=source.itad_shop_id,
                ),
                proton_db_info=proton_db_info,
            )


def _get_source(conn: Connection, name: str) -> Row:
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
    conn: Connection, game: ScrapedSteamGame, source_id: int, appid: str
) -> int:
    """Return existing game_id, or insert a new game + external-id row."""
    existing = conn.execute(
        select(game_external_id_table.c.game_id).where(
            game_external_id_table.c.source_id == source_id,
            game_external_id_table.c.external_id == appid,
        )
    ).first()

    if existing is not None:
        return existing.game_id

    result = conn.execute(
        game_table.insert().values(
            title=game.title,
            product_type=ProductType_(game.product_type),
        )
    )
    game_id: int = result.inserted_primary_key[0]  # type: ignore[assignment]

    conn.execute(
        sqlite_insert(game_external_id_table)
        .values(game_id=game_id, source_id=source_id, external_id=appid)
        .on_conflict_do_nothing(index_elements=["source_id", "external_id"])
    )

    return game_id


def _insert_cost(
    conn: Connection, game_id: int, source_id: int, game: ScrapedSteamGame
) -> CostData | None:
    if game.cost is None:
        return None

    cost = game.cost
    now = datetime.datetime.now(datetime.timezone.utc)

    result = conn.execute(
        cost_table.insert().values(
            game_id=game_id,
            source_id=source_id,
            country_alpha2=cost.country_l2,
            currency=cost.currency_3l,
            collected_date=None,  # TODO: scraper does not provide this yet
            insertion_date=now,
            value_minor=cost.value_minor,
            full_value_minor=cost.full_value_minor,
            discount=cost.discount,
            flag=None,
            price_expires_at=None,
            url=game.link,
        )
    )
    cost_id: int = result.inserted_primary_key[0]  # type: ignore[assignment]

    return CostData(
        id=cost_id,
        value_minor=cost.value_minor,
        currency_3l=cost.currency_3l,
        full_value_minor=cost.full_value_minor,
        discount=cost.discount,
        country_l2=cost.country_l2,
        price_expires_at=None,
        observed_date=None,
        historical_deal=None,
    )


def _insert_proton_report(
    conn: Connection,
    game_id: int,
    report: ScrapedProtonDBReport | None,
) -> ProtonDBReportV2 | None:
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

    return ProtonDBReportV2(
        game_id=game_id,
        best_reported_tier=ProtonDBTier(report.best_reported_tier),
        confidence=report.confidence,
        score=report.score,
        tier=ProtonDBTier(report.tier),
        total=report.total,
        trending_tier=ProtonDBTier(report.trending_tier),
    )
