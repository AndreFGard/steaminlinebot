import datetime
import enum
from typing import Optional

import pydantic

from steaminlinebot.game.protondb_report import ProtonDBReport
from steaminlinebot.integration.protondb_client import ScrapedProtonDBReport


class ProductType(enum.Enum):
    GAME = "game"
    APPLICATION = "application"
    TOOL = "tool"
    DEMO = "demo"
    DLC = "dlc"
    MUSIC = "music"
    MOD = "mod"


class HistoricalDeal(enum.Enum):
    """If the deal is a historical low or not"""

    HISTORICAL_LOW = "H"
    NEW_HISTORICAL_LOW = "N"
    STORE_LOW = "S"


class GameDeal(pydantic.BaseModel):
    value_minor: int
    currency_3l: str
    full_value_minor: int
    """Follows the standardized currency representation"""
    discount: int
    country_l2: Optional[str]
    price_expires_at: Optional[datetime.datetime]
    observed_date: Optional[datetime.datetime]
    # TODO change for historical deal again
    """If the current price is a historical low or not"""
    historical_deal: Optional[LowestPriceInPeriod]
    url: str
    source_shop: str


class COMMON_GAME_SOURCE_NAMES(enum.Enum):
    """Non exhaustive list of supported game sources. The name must be the same that ITAD uses"""

    STEAM = "Steam"
    ITAD = "ITAD"


class Game(pydantic.BaseModel):
    id: int
    """Canonical id"""
    title: str
    product_type: ProductType


class LowestPriceInPeriod(enum.Enum):
    ALL = "all"
    YEAR = "y1"
    QUARTER = "m3"


# TODO: this class is in the DB, but not yet wired in.
class HistoricalPriceData(pydantic.BaseModel):
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


# TODO break this down into a repository DTO, or destroy it altogether.
class ScrapedSteamGame(pydantic.BaseModel):
    """Steam scraping result"""

    link: str
    title: str
    appid: str
    cost: Optional[ScrapedCost]
    is_free: bool
    proton_db_report: Optional[ScrapedProtonDBReport] = None
    # TODO make enum
    product_type: ProductType


class SourcedGame(pydantic.BaseModel):
    game: Game
    external_id: str
    game_source: COMMON_GAME_SOURCE_NAMES
    main_deal: Optional[GameDeal]
    other_deals: list[GameDeal]
    url: str
    price_overview: Optional[HistoricalPriceData]
    """Only exists for games available on steam"""
    proton_db_info: Optional[ProtonDBReport]
