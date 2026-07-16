import logging
from dataclasses import dataclass
from sqlite3 import Connection
from typing import Optional

from modules.db.UserRepository import UserRepository


@dataclass
class CountryModification:
    configured_country: Optional[str]
    requested_country: str
    """Might be None if unsuccessful"""
    alternative_suggestions: list[str]


@dataclass
class CountryConfig:
    country: str
    has_configured: bool


class UserCountry:
    def __init__(self, db: Connection):
        self._user_repo = UserRepository(db)

    def get_country(self, user_id: int, fallback_languages=None):
        if fallback_languages is None:
            fallback_languages = []
        country = self._user_repo.get_user_country(user_id)
        has_set = True
        if not country:
            has_set = False
            for lang in fallback_languages:
                country = self._user_repo.get_country_by_language(lang)
                if country:
                    break

        if not country:
            country = "US"
        return CountryConfig(country=country, has_configured=has_set)

    async def set_country(self, user_id: int, country: str, user_lang: str):
        requested_country = country
        country = country.upper()
        try:
            success = self._user_repo.upsert_user_country(user_id, country)
        except Exception as e:
            success = False
            logging.error(f"set_country error: {e}")
        if success:
            return CountryModification(
                configured_country=country,
                requested_country=requested_country,
                alternative_suggestions=[],
            )

        # language based suggestion
        suggestion = self._user_repo.get_country_by_language(user_lang)
        codes = {"PT", "PL", "BR", "US"}
        if suggestion:
            codes.add(suggestion)

        return CountryModification(
            configured_country=country,
            requested_country=requested_country,
            alternative_suggestions=list(reversed(list(codes))),
        )

    def delete_user(self, user_id: int) -> bool:
        """Delete user data. Returns True if successful."""
        try:
            self._user_repo.delete_user(user_id)
            return True
        except Exception as e:
            logging.error(f"delete_user error: {e}")
            return False

    async def parse_set_currency_command(
        self, args: list[str] | None, user_id: int, lang_etf: str
    ) -> CountryModification:
        lang = lang_etf.split("-")[0].lower()

        if args:
            requested_country = args[0]
            return await self.set_country(user_id, requested_country, lang)

        # No args - provide suggestions
        local_suggestion = self._user_repo.get_country_by_language(lang)
        target_codes = ["BR", "US", "MX", "PL"]
        if local_suggestion and local_suggestion not in target_codes:
            target_codes.insert(0, local_suggestion)

        return CountryModification(
            configured_country=None,
            requested_country="",
            alternative_suggestions=target_codes,
        )
