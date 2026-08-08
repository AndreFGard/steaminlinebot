import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.database.UserRepository import IUserRepository


class IUserCountry(ABC):
    """Resolves and persists user currency/country preferences."""

    @abstractmethod
    def get_country(
        self,
        user_id: int,
        fallback_languages: list[str] | None = None,
    ) -> CountryConfig: ...

    @abstractmethod
    def delete_user(self, user_id: int) -> bool: ...

    @abstractmethod
    async def set_country(
        self, user_id: int, country: str, user_lang: str
    ) -> CountryModification: ...
    @abstractmethod
    async def get_country_by_language(self, language_code: str) -> str | None: ...


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


class UserCountry(IUserCountry):
    def __init__(self, user_repo: IUserRepository):
        self._user_repo = user_repo

    async def get_country_by_language(self, language_code: str):
        return self._user_repo.get_country_by_language(language_code)

    def get_country(self, user_id: int, fallback_languages=None):
        if fallback_languages is None:
            fallback_languages = []
        country = self._user_repo.get_user_country(user_id)
        has_set = True
        if not country:
            has_set = False
            # TODO: language→country inference is a naive prefix match
            # (longest tag wins).  A better approach would use a proper
            # locale→territory mapping (e.g. BCP-47 / CLDR supplemental
            # data) that can handle bare "en" → US, "zh" → CN, etc.
            # without relying on coincidental seed-data ordering.
            for lang in fallback_languages:
                country = self._user_repo.get_country_by_language(lang)
                if country:
                    break

        if not country:
            country = "US"
        return CountryConfig(country=country, has_configured=has_set)

    async def set_country(
        self, user_id: int, country: str, user_lang: str
    ) -> CountryModification:
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
