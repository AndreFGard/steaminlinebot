from abc import ABC
import datetime
from enum import Enum
import logging
from typing import Any, NewType, Optional

import aiohttp
import pydantic


class ITADPrice(pydantic.BaseModel):
    amount: float
    amountInt: int
    currency_3l: str


class ITADHistoricalLowInfo(pydantic.BaseModel):
    all: Optional[ITADPrice]
    """Best of all times"""
    y1: Optional[ITADPrice]
    """Best in a year"""
    m3: Optional[ITADPrice]


class ITADDealFlag(Enum):
    Historical = "H"
    NewHistorical = "N"
    StoreLow = "S"


class ITADDeal(pydantic.BaseModel):
    shop_id: int
    shop_name: str
    price: ITADPrice
    regular: ITADPrice
    cut: int
    """Integer 0-100"""
    store_low: Optional[ITADPrice]
    deal_flag: Optional[ITADDealFlag]
    expiry: Optional[datetime.datetime]


class ITADPriceOverview(pydantic.BaseModel):
    id: str
    historical_low: ITADHistoricalLowInfo
    deals: list[ITADDeal]


ITADGameId = NewType("ITADGameId", str)

ITADShopId = NewType("ITADShopId", int)


class ITADShop(pydantic.BaseModel):
    title: str
    id: ITADShopId


class ITADGameLookup(pydantic.BaseModel): ...


class IITADClient(ABC):
    # TODO add shop_id restriction
    async def get_prices(
        self, game_ids: list[ITADGameId], country_2l: str
    ) -> list[ITADPriceOverview | None]:
        """Up to 200 game ids"""
        ...


class ITADApiError(Exception): ...


class ITADClient(IITADClient):
    def __init__(self, key: str, session: aiohttp.ClientSession):
        self._session = session
        self._key = key
        self._auth_headers = {"ITAD-API-Key": self._key}

    async def get_prices(
        self, game_ids: list[ITADGameId], country_2l: str
    ) -> list[ITADPriceOverview | None]:
        URL = "https://api.isthereanydeal.com/games/prices/v3"

        params = {
            "country": country_2l,
        }
        req_body = game_ids

        res = await self._session.get(
            URL, json=req_body, headers=self._auth_headers, params=params
        )
        if res.status != 200:
            raise ITADApiError(await res.json())

        res_body: dict = await res.json()

        overviews: dict[ITADGameId, ITADPriceOverview | None] = {
            game_id: None for game_id in game_ids
        }

        for price_overview_json in res_body:
            try:
                price_overview = ITADPriceOverview.model_validate(
                    price_overview_json, extra="allow"
                )
                overviews[ITADGameId(price_overview.id)] = price_overview
            except Exception as e:
                logging.error(
                    f"Got error in validation of ITAD price_overview: {price_overview_json}; {e}"
                )

        return list(overviews.values())

    async def get_shop_map(self) -> list[ITADShop]:
        URL = "https://api.isthereanydeal.com/service/shops/map/v1"
        res = await self._session.get(URL, headers=self._auth_headers)

        shops: list[ITADShop] = []
        for shop in await res.json():
            shops.append(ITADShop(title=shop["title"], id=ITADShopId(int(shop["id"]))))

        return shops

    # Only supports steam because it requires a specific syntax for  the steam appid.
    async def lookup_by_steam_shopid(
        self, shop_id: int, game_ids: list[int]
    ) -> dict[int, str | None]:
        URL = f"https://api.isthereanydeal.com/lookup/id/shop/{shop_id}/v1"

        body = [f"app/{id}" for id in game_ids]
        res = await self._session.post(URL, json=body, headers=self._auth_headers)
        json = await res.json()

        # app/220 -> app/220: itadId
        return {int(game.split("/")[1]): itadId for game, itadId in json.items()}
