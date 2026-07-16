import sqlite3
from dataclasses import dataclass
from pydantic import BaseModel
from typing import Optional
import aiohttp

class GGDealsAPIPrices(BaseModel):
    currentRetail: Optional[str] = None
    currentKeyshops: Optional[str] = None
    historicalRetail: Optional[str] = None
    historicalKeyshops: Optional[str] = None
    currency: str
    

class GGDealsResultItem(BaseModel):
    title: str
    url: str
    prices: GGDealsAPIPrices

class GGDealsGame(GGDealsResultItem):
    appid: str

class GGDealsAPIError(BaseModel):
    name: str
    message: str
    code: int
    status: int

class GGDealsResponse(BaseModel):
    success: bool
    data: dict[str, GGDealsResultItem] | GGDealsAPIError

class GGDealsException(Exception):
    ...
class GGDealsRateLimit(GGDealsException):
    ...

class GGDealsAPI:
    def __init__(self, apikey:str):
        assert apikey
        self._key = apikey
    
    async def searchAppids(self, country:str, appids: list[str])-> list[GGDealsGame]:
        country = country.lower()
        url = 'https://api.gg.deals/v1/GGDealsAPIPrices/by-steam-app-id/'
        params = {
            "ids": appids,
            "key": self._key,
            'region': country
        } 
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as res:
                if res.status != 200:
                    if res.status == 429:
                        raise GGDealsRateLimit()
                    else: raise GGDealsException(res.text())
                    
                data = GGDealsResponse(**(await res.json()))

                if isinstance(data.data, GGDealsAPIError):
                    raise GGDealsException(res.text())

                games = [
                    GGDealsGame(
                        title=vals.title,
                        appid=appid,
                        url = vals.url,
                        prices= vals.prices,
                        )
                        for appid,vals in data.data.items() ]
                return games
                





    