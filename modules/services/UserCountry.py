import logging
from sqlite3 import Connection

from dataclasses import dataclass
import time

from telegram import Update

from modules.SteamSearcher import SteamSearcher
from modules.db.UserRepository import UserRepository
from modules.db.GameResultRepository import GameResultRepository
from typing import Optional
from pydantic import BaseModel
from modules.ProtonDBReport import ProtonDBReport, ProtonDBTier


@dataclass
class CountryConfig:
    configuredCountry: Optional[str]
    """Might be None if unsuccessful"""
    alternativeSuggestions: list[str]


class UserCountry:
    def __init__(self, db:Connection):
        self._userRepo = UserRepository(db)

    def get_country(self, userId:int, fallback_languages=[]):
        country = self._userRepo.get_user_country(userId)
        has_set=True
        if not country:
            has_set = False
            for l in fallback_languages:
                country = self._userRepo.get_country_by_language(l)
                if country: break

        if not country: country = "US"
        return (has_set,country )

    async def setCountry(self, userId: int, country:str, userLang:str):
        country = country.upper()
        try:
            success = self._userRepo.upsert_user_country(userId, country)
        except Exception as e :
            success = False
            logging.error(f"setCountry errro: {e}")
        if success:
            return CountryConfig(country, [])
        
        #language based suggestion
        suggestion = self._userRepo.get_country_by_language(userLang)
        codes = {"PT", "PL", "BR", "US"}
        if suggestion: codes.add(suggestion)

        return CountryConfig(None, list(reversed(list(codes))))
        


