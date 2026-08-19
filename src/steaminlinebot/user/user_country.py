import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.database.UserRepository import IUserRepository

# --- constants ---
_DEFAULT_COUNTRY = "US"
_DEFAULT_LANGUAGE = "en"
_DEFAULT_FALLBACK_LANGUAGE_ETF = "en-US"
_POPULAR_COUNTRY_CODES = ["BR", "US", "MX", "PL"]


@dataclass
class CountryModification:
    """Might be None if unsuccessful"""

    configured_country: Optional[str]
    requested_country: str


@dataclass
class CountryConfig:
    country: str
    has_configured: bool


@dataclass
class CountrySetResult:
    modification: Optional[CountryModification]
    suggestions: list[str]


# TODO: this class is depended by way too many files
class IUserCountry(ABC):
    """Resolves and persists user currency/country preferences."""

    @abstractmethod
    async def resolve_country(
        self, user_id: int, fallback_user_language_etf: Optional[str]
    ) -> CountryConfig: ...

    @abstractmethod
    async def delete_user(self, user_id: int) -> bool: ...

    @abstractmethod
    async def set_country(
        self, user_id: int, requested_country: str, user_lang_2l: Optional[str] = None
    ) -> CountrySetResult: ...

    @abstractmethod
    async def suggest_countries(self, lang_2l: Optional[str]) -> list[str]:
        """Returns a list of likely countries for the user, based on a language-only tag, or None."""
        ...


class UserCountry(IUserCountry):
    def __init__(self, user_repo: IUserRepository):
        self._user_repo = user_repo

    async def get_country_by_language_2l(self, language_2l: str):
        if len(language_2l) != 2:
            raise ValueError(
                f"language_2l must be a 2-letter code, got '{language_2l}'"
            )
        return self._user_repo.get_country_by_language(language_2l)

    async def get_country_by_language_etf(self, language_etf: str):
        if len(language_etf) != 2:
            raise ValueError(
                f"language_2l must be a 2-letter code, got '{language_etf}'"
            )
        return self._user_repo.get_country_by_language(language_etf)

    async def resolve_country(
        self, user_id: int, fallback_user_language_etf: Optional[str]
    ) -> CountryConfig:
        country = self._user_repo.get_user_country(user_id)
        has_set = True

        if not country:
            has_set = False
            # TODO: language→country inference is a naive prefix match. A better approach would use a proper locale -> country to avoid bad guesses.
            if not fallback_user_language_etf:
                fallback_user_language_etf = _DEFAULT_FALLBACK_LANGUAGE_ETF
            country = await self.get_country_by_language_2l(
                fallback_user_language_etf.split("-")[0]
            )

        if not country:
            country = _DEFAULT_COUNTRY
        return CountryConfig(country=country, has_configured=has_set)

    async def set_country(
        self, user_id: int, requested_country: str, user_lang_2l: Optional[str] = None
    ) -> CountrySetResult:
        suggestions = await self.suggest_countries(user_lang_2l)

        if not requested_country:
            return CountrySetResult(modification=None, suggestions=suggestions)

        assert len(requested_country) == 2
        used_country = requested_country.upper()

        try:
            success = self._user_repo.upsert_user_country(user_id, used_country)
        except Exception as e:
            success = False
            logging.error(f"set_country error: {e}")

        if success:
            modification = CountryModification(
                configured_country=used_country,
                requested_country=requested_country,
            )
        else:
            modification = CountryModification(
                configured_country=None, requested_country=requested_country
            )

        return CountrySetResult(modification=modification, suggestions=suggestions)

    async def suggest_countries(self, lang_2l: Optional[str]) -> list[str]:
        if not lang_2l:
            logging.warning("Suggesting default-based language")
            lang_2l = _DEFAULT_LANGUAGE

        language_inferred_country = await self.get_country_by_language_2l(lang_2l)
        suggested_country_codes = list(_POPULAR_COUNTRY_CODES)
        if language_inferred_country:
            suggested_country_codes.append(language_inferred_country)
        # inferred appears earlier; preserve order while deduplicating.
        suggested_country_codes = list(dict.fromkeys(reversed(suggested_country_codes)))

        return suggested_country_codes

    async def delete_user(self, user_id: int) -> bool:
        """Delete user data. Returns True if successful."""
        try:
            self._user_repo.delete_user(user_id)
            return True
        except Exception as e:
            logging.error(f"delete_user error: {e}")
            return False
