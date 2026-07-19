from abc import ABC, abstractmethod
import logging

from steaminlinebot.user.UserCountry import CountryModification, IUserCountry


class IUserCountryUsecase(ABC):
    """Application use case: user country/currency management.

    Orchestrates country resolution, currency setting, and user data
    deletion.  Keeps the Telegram adapter (Bot) unaware of repositories.
    """

    @abstractmethod
    async def delete_user_info(self, user_id: int) -> bool: ...

    @abstractmethod
    async def set_currency(
        self,
        user_id: int,
        user_language_etf: str | None,
        country: str | None,
    ) -> CountryModification: ...

    @abstractmethod
    async def suggest_currencies(self, lang: str) -> CountryModification: ...


class UserCountryUsecase(IUserCountryUsecase):
    def __init__(self, user_country: IUserCountry):
        self._user_country = user_country

    async def delete_user_info(self, user_id: int) -> bool:
        success = self._user_country.delete_user(user_id)
        return success

    async def set_currency(
        self,
        user_id: int,
        user_language_etf: str | None,
        country: str | None,
    ) -> CountryModification:
        """/setcurrency command, sending a keyboard, not callback"""
        user_language_etf = user_language_etf or "en-us"
        language_code = user_language_etf.split("-")[0].lower()

        country = country or await self._user_country.get_country_by_language(
            language_code
        )
        if country is None:
            raise ValueError(
                f"No country was provided nor obtained by the language {user_language_etf}"
            )

        country_mod = await self._set_currency(country, user_id, language_code)
        return country_mod

    async def suggest_currencies(self, lang: str) -> CountryModification:
        if not lang:
            logging.warning("Suggesting default-based language")

        language_inferred_country = await self._user_country.get_country_by_language(
            lang or "en"
        )
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

    async def _set_currency(
        self, requested_country: str, user_id: int, lang: str
    ) -> CountryModification:

        return await self._user_country.set_country(user_id, requested_country, lang)
