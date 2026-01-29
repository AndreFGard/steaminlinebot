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
class CountryModification:
    configuredCountry: Optional[str]
    requestedCountry: str
    """Might be None if unsuccessful"""
    alternativeSuggestions: list[str]

@dataclass
class CountryConfig:
    country: str
    hasConfigured:bool

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
        return CountryConfig(country=country, hasConfigured=has_set)

    async def setCountry(self, userId: int, country:str, userLang:str):
        requestedCountry = country
        country = country.upper()
        try:
            success = self._userRepo.upsert_user_country(userId, country)
        except Exception as e :
            success = False
            logging.error(f"setCountry error: {e}")
        if success:
            return CountryModification(
                configuredCountry=country,
                requestedCountry=requestedCountry,
                alternativeSuggestions=[])
        
        #language based suggestion
        suggestion = self._userRepo.get_country_by_language(userLang)
        codes = {"PT", "PL", "BR", "US"}
        if suggestion: codes.add(suggestion)

        return CountryModification(
            configuredCountry=country,
            requestedCountry=requestedCountry,
            alternativeSuggestions=list(reversed(list(codes))))

    def deleteUser(self, userId: int) -> bool:
        """Delete user data. Returns True if successful."""
        try:
            self._userRepo.delete_user(userId)
            return True
        except Exception as e:
            logging.error(f"deleteUser error: {e}")
            return False

    async def parseSetCurrencyCommand(self, args: list[str]|None, userId: int, userLang: str) -> CountryModification:
        if args:
            requested_country = args[0]
            return await self.setCountry(userId, requested_country, userLang)
        
        # No args - provide suggestions
        local_suggestion = self._userRepo.get_country_by_language(userLang)
        target_codes = ["BR", "US", "MX", "PL"]
        if local_suggestion and local_suggestion not in target_codes:
            target_codes.insert(0, local_suggestion)
        
        return CountryModification(
            configuredCountry=None,
            requestedCountry="",
            alternativeSuggestions=target_codes
        )
    


