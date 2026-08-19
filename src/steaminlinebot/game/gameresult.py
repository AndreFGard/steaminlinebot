import enum
import datetime
from typing import Literal, Optional


import pydantic

from steaminlinebot.game.protondb_report import ProtonDBReport
from steaminlinebot.integration.protondb_client import ScrapedProtonDBReport


class HistoricalDeal(enum.Enum):
    """If the deal is a historical low or not"""

    HISTORICAL_LOW = "H"
    NEW_HISTORICAL_LOW = "N"
    STORE_LOW = "S"


class CostData(pydantic.BaseModel):
    id: int
    value_minor: int
    currency_3l: str
    full_value_minor: int
    """Represented as 4 decimals (99.99 -> 9999)"""
    discount: int
    country_l2: Optional[str]
    price_expires_at: Optional[datetime.datetime]
    observed_date: Optional[datetime.datetime]
    """If the current price is a historical low or not"""
    historical_deal: Optional[HistoricalDeal]


class GameSourceInfo(pydantic.BaseModel):
    """GameSource is any index of games. can be used to translate internal -> external id"""

    source_name: str
    external_id: str
    itad_shop_id: Optional[str]


class LowestPriceInPeriod(enum.Enum):
    ALL = "all"
    YEAR = "y1"
    QUARTER = "m3"


# TODO: this class is in the DB, but not yet wired in.
class HistoricPriceOverview:
    game_id: int
    scope: LowestPriceInPeriod
    lowest_value_minor: int
    country_l2: str
    currency_3l: str


class ScrapedCost(pydantic.BaseModel):
    """Cost data from scraping"""

    value_minor: int
    currency_3l: str
    full_value_minor: int
    discount: int
    country_l2: str


# TODO does not belong here.
class ScrapedSteamGame(pydantic.BaseModel):
    """Steam scraping result"""

    link: str
    title: str
    appid: str
    cost: Optional[ScrapedCost]
    is_free: bool
    proton_db_report: Optional[ScrapedProtonDBReport] = None
    product_type: Literal[
        "game", "application", "tool", "demo", "dlc", "music", "mod"
    ] = "game"


class GameResult(pydantic.BaseModel):
    id: int
    title: str
    product_type: Literal[
        "game", "application", "tool", "demo", "dlc", "music", "mod"
    ] = "game"
    cost: Optional[CostData]
    url: str
    game_source: GameSourceInfo
    """Only exists for steam games"""
    proton_db_info: Optional[ProtonDBReport]
