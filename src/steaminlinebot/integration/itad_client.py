import datetime
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import NewType

import aiohttp
import pydantic

log = logging.getLogger(__name__)

_PRICES_URL = "https://api.isthereanydeal.com/games/prices/v3"
_SHOP_MAP_URL = "https://api.isthereanydeal.com/service/shops/map/v1"


class _ITADModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow", populate_by_name=True)


class ITADPrice(_ITADModel):
    amount: float
    amount_int: int = pydantic.Field(alias="amountInt")
    currency_3l: str


class ITADHistoricalLowInfo(_ITADModel):
    all: ITADPrice | None = None  # Best of all times.
    y1: ITADPrice | None = None  # Best in a year.
    m3: ITADPrice | None = None


class ITADDealFlag(Enum):
    Historical = "H"
    NewHistorical = "N"
    StoreLow = "S"


class ITADDeal(_ITADModel):
    shop_id: int
    shop_name: str
    price: ITADPrice
    regular: ITADPrice
    cut: int
    """Integer 0-100."""
    store_low: ITADPrice | None = None
    deal_flag: ITADDealFlag | None = None
    expiry: datetime.datetime | None = None


class ITADPriceOverview(_ITADModel):
    id: str
    historical_low: ITADHistoricalLowInfo
    deals: list[ITADDeal]


ITADGameId = NewType("ITADGameId", str)

ITADShopId = NewType("ITADShopId", int)


class ITADShop(_ITADModel):
    title: str
    id: ITADShopId


class IITADClient(ABC):
    """Interface for the ITAD API client."""

    # TODO add shop_id restriction.
    @abstractmethod
    async def get_prices(
        self, game_ids: list[ITADGameId], country_2l: str
    ) -> list[ITADPriceOverview | None]:
        """Fetch current prices for up to 200 game ids."""
        ...

    @abstractmethod
    async def get_shop_map(self) -> list[ITADShop]:
        """Fetch the map of shop ids to shop names."""
        ...

    @abstractmethod
    async def lookup_by_steam_shopid(
        self, game_ids: list[int]
    ) -> dict[int, str | None]:
        """Map Steam app ids to ITAD game ids."""
        ...


class ITADApiError(Exception):
    """Raised when the ITAD API returns an unsuccessful response."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"ITAD API error {status}: {body}")
        self.status = status
        self.body = body


class ITADClient(IITADClient):
    def __init__(self, key: str, steam_shop_id: int, session: aiohttp.ClientSession):
        self._session = session
        self._key = key
        self._auth_headers = {"ITAD-API-Key": self._key}
        self._steam_shop_id = steam_shop_id

    async def _raise_for_status(self, res: aiohttp.ClientResponse) -> None:
        if res.status != 200:
            raise ITADApiError(res.status, await res.text())

    async def get_prices(
        self, game_ids: list[ITADGameId], country_2l: str
    ) -> list[ITADPriceOverview | None]:
        res = await self._session.get(
            _PRICES_URL,
            json=game_ids,
            headers=self._auth_headers,
            params={"country": country_2l},
        )
        await self._raise_for_status(res)

        res_body: dict[str, object] = await res.json()

        overviews: dict[ITADGameId, ITADPriceOverview | None] = {
            game_id: None for game_id in game_ids
        }

        for game_id, price_overview_json in res_body.items():
            try:
                overviews[ITADGameId(game_id)] = ITADPriceOverview.model_validate(
                    price_overview_json
                )
            except pydantic.ValidationError as e:
                log.error("Invalid ITAD price overview for %s: %s", game_id, e)

        return list(overviews.values())

    async def get_shop_map(self) -> list[ITADShop]:
        res = await self._session.get(_SHOP_MAP_URL, headers=self._auth_headers)
        await self._raise_for_status(res)

        return [ITADShop.model_validate(shop) for shop in await res.json()]

    async def lookup_by_steam_shopid(
        self, game_ids: list[int]
    ) -> dict[int, str | None]:
        """Map Steam app ids to ITAD game ids.

        Only supports Steam because it requires the ``app/<id>`` syntax.
        """
        url = f"https://api.isthereanydeal.com/lookup/id/shop/{self._steam_shop_id}/v1"
        body = [f"app/{app_id}" for app_id in game_ids]
        res = await self._session.post(url, json=body, headers=self._auth_headers)
        await self._raise_for_status(res)

        lookup = await res.json()

        # app/220 -> 220: ITAD game id.
        return {int(game.split("/")[1]): itad_id for game, itad_id in lookup.items()}
