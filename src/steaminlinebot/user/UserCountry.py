import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.database.UserRepository import IUserRepository


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


# TODO: this class is depended by way too many files
class IUserCountry(ABC):
    """Resolves and persists user currency/country preferences."""

    @abstractmethod
    def get_country(
        self,
        user_id: int,
        fallback_languages: list[str] | None = None,
    ) -> CountryConfig: ...

    @abstractmethod
    async def delete_user(self, user_id: int) -> bool: ...

    @abstractmethod
    async def set_country(
        self, user_id: int, requested_country: str, user_lang_etf: str
    ) -> CountryModification: ...
    @abstractmethod
    async def get_country_by_language(self, language_code: str) -> str | None: ...

    @abstractmethod
    async def suggest_currencies(self, lang: str) -> CountryModification: ...


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
            # TODO: language→country inference is a naive prefix match. A better approach would use a proper locale -> country to avoid bad guesses.
            for lang in fallback_languages:
                country = self._user_repo.get_country_by_language(lang)
                if country:
                    break

        if not country:
            country = "US"
        return CountryConfig(country=country, has_configured=has_set)

    async def set_country(
        self, user_id: int, requested_country: str, user_lang_etf: str
    ) -> CountryModification:
        user_lang_2l = user_lang_etf.split("-")[0]

        if requested_country:
            used_country = requested_country.upper()
        else:
            used_country = await self.get_country_by_language(user_lang_2l)
            if not used_country:
                raise ValueError(
                    f"No country was provided nor obtained by the language {user_lang_2l}"
                )

        try:
            success = self._user_repo.upsert_user_country(user_id, used_country)
        except Exception as e:
            success = False
            logging.error(f"set_country error: {e}")

        if success:
            return CountryModification(
                configured_country=used_country,
                requested_country=requested_country,
                alternative_suggestions=[],
            )

        # language based suggestion
        suggestion = self._user_repo.get_country_by_language(user_lang_etf)
        codes = {"BR", "US", "MX", "PL"}
        if suggestion:
            codes.add(suggestion)

        return CountryModification(
            configured_country=used_country,
            requested_country=requested_country,
            alternative_suggestions=list(reversed(list(codes))),
        )

    async def suggest_currencies(self, lang: str) -> CountryModification:
        if not lang:
            logging.warning("Suggesting default-based language")

        language_inferred_country = await self.get_country_by_language(lang or "en")
        suggested_country_codes = ["BR", "US", "MX", "PL"]
        if language_inferred_country:
            suggested_country_codes.append(language_inferred_country)
        # inferred appears earlier.
        suggested_country_codes = list(set(reversed(suggested_country_codes)))

        return CountryModification(
            configured_country=None,
            requested_country="",
            alternative_suggestions=suggested_country_codes,
        )

    async def delete_user(self, user_id: int) -> bool:
        """Delete user data. Returns True if successful."""
        try:
            self._user_repo.delete_user(user_id)
            return True
        except Exception as e:
            logging.error(f"delete_user error: {e}")
            return False
