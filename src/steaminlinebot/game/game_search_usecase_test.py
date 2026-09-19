from unittest.mock import AsyncMock

import pytest

import steaminlinebot.user.user_country
import steaminlinebot.game.game_searcher_service
from steaminlinebot.game import game_search_usecase
from steaminlinebot.game.game_search_usecase import QueryTooShortError
from steaminlinebot.user.user_country import CountryConfig


VALID_COUNTRY = "FR"
USER_COUNTRY = "BR"


class GameSearchUsecaseFixture:
    def __init__(self):
        self.user_country = AsyncMock(
            spec=steaminlinebot.user.user_country.IUserCountry
        )
        self.game_search = AsyncMock(
            spec=steaminlinebot.game.game_searcher_service.IGameSearcherService
        )

        self.usecase = game_search_usecase.GameSearchUsecase(
            self.user_country, self.game_search
        )

    def given_resolved_country(self, country: str, has_configured: bool):
        self.user_country.resolve_country.return_value = CountryConfig(
            country=country, has_configured=has_configured
        )

    def given_search_results(self, results: list):
        self.game_search.search_game.return_value = results

    async def when_searching(self, query: str):
        return await self.usecase.handle_game_search(
            query, user_id=0, user_lang_etf=None
        )


@pytest.fixture
def usecase_fixture():
    return GameSearchUsecaseFixture()


async def test_inline_country_config(usecase_fixture: GameSearchUsecaseFixture):
    usecase_fixture.given_resolved_country(VALID_COUNTRY, True)
    result = await usecase_fixture.when_searching(f"/{VALID_COUNTRY} something")

    assert result.country_config == CountryConfig(
        country=VALID_COUNTRY, has_configured=True
    )
    usecase_fixture.game_search.search_game.assert_awaited_once_with(
        "something", country_2l=VALID_COUNTRY
    )


async def test_lowercase_inline_country_is_normalized(
    usecase_fixture: GameSearchUsecaseFixture,
):
    usecase_fixture.user_country.is_valid_country.return_value = True

    result = await usecase_fixture.when_searching(f"/{VALID_COUNTRY.lower()} something")

    assert result.country_config == CountryConfig(
        country=VALID_COUNTRY, has_configured=True
    )
    usecase_fixture.user_country.is_valid_country.assert_awaited_once_with(
        VALID_COUNTRY
    )
    usecase_fixture.game_search.search_game.assert_awaited_once_with(
        "something", country_2l=VALID_COUNTRY
    )


async def test_invalid_inline_country_falls_back_to_user_country(
    usecase_fixture: GameSearchUsecaseFixture,
):
    usecase_fixture.user_country.is_valid_country.return_value = False
    usecase_fixture.given_resolved_country(USER_COUNTRY, has_configured=True)

    result = await usecase_fixture.when_searching("/XX something")

    assert result.country_config == CountryConfig(
        country=USER_COUNTRY, has_configured=True
    )
    # invalid prefix is not stripped from the query
    usecase_fixture.game_search.search_game.assert_awaited_once_with(
        "/XX something", country_2l=USER_COUNTRY
    )


async def test_no_inline_country_uses_user_country(
    usecase_fixture: GameSearchUsecaseFixture,
):
    usecase_fixture.given_resolved_country(USER_COUNTRY, has_configured=False)

    result = await usecase_fixture.when_searching("skyrim")

    assert result.country_config == CountryConfig(
        country=USER_COUNTRY, has_configured=False
    )
    usecase_fixture.game_search.search_game.assert_awaited_once_with(
        "skyrim", country_2l=USER_COUNTRY
    )


async def test_country_prefix_mid_query_is_not_recognized(
    usecase_fixture: GameSearchUsecaseFixture,
):
    usecase_fixture.user_country.is_valid_country.return_value = True
    usecase_fixture.given_resolved_country(USER_COUNTRY, has_configured=False)

    result = await usecase_fixture.when_searching(f"skyrim /{VALID_COUNTRY}")

    assert result.country_config == CountryConfig(
        country=USER_COUNTRY, has_configured=False
    )
    usecase_fixture.game_search.search_game.assert_awaited_once_with(
        f"skyrim /{VALID_COUNTRY}", country_2l=USER_COUNTRY
    )


async def test_spaces_after_country_prefix_are_stripped(
    usecase_fixture: GameSearchUsecaseFixture,
):
    usecase_fixture.user_country.is_valid_country.return_value = True

    await usecase_fixture.when_searching(f"/{VALID_COUNTRY}  half-life")

    usecase_fixture.game_search.search_game.assert_awaited_once_with(
        "half-life", country_2l=VALID_COUNTRY
    )


async def test_search_results_are_passed_through(
    usecase_fixture: GameSearchUsecaseFixture,
):
    usecase_fixture.given_resolved_country(USER_COUNTRY, has_configured=False)
    expected_results = [object()]

    usecase_fixture.given_search_results(expected_results)
    result = await usecase_fixture.when_searching("skyrim")

    assert result.search_results is expected_results


async def test_minimum_length_query_is_accepted(
    usecase_fixture: GameSearchUsecaseFixture,
):
    usecase_fixture.given_resolved_country(USER_COUNTRY, has_configured=False)

    await usecase_fixture.when_searching("abc")

    usecase_fixture.game_search.search_game.assert_awaited_once_with(
        "abc", country_2l=USER_COUNTRY
    )


async def test_query_too_short_raises(
    usecase_fixture: GameSearchUsecaseFixture,
):
    query = "/US ab"
    usecase_fixture.user_country.is_valid_country.return_value = True

    with pytest.raises(QueryTooShortError):
        await usecase_fixture.when_searching(query)

    query = "ab"
    usecase_fixture.user_country.is_valid_country.return_value = True

    with pytest.raises(QueryTooShortError):
        await usecase_fixture.when_searching(query)
