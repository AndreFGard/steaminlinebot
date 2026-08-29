from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import uuid4

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
)

from steaminlinebot.game import core
from steaminlinebot.game.game_search_usecase import GameSearchResult
from steaminlinebot.game.game_searcher_service import (
    GameResultVM,
    ProtonDBVM,
)
from steaminlinebot.user.user_country import CountryConfig, CountryModification


class SpecialResults(Enum):
    NO_MATCHES = 1
    ERROR = 2
    QUERY_TOO_SHORT = 4


@dataclass
class TelegramPresentation:
    keyboard: InlineKeyboardMarkup
    text: str
    parse_mode: str

    def __post_init__(self):
        if self.parse_mode not in ["HTML", "Markdown"]:
            raise ValueError("parse_mode must be either 'HTML' or 'Markdown'")


@dataclass
class TelegramInlineArticlePres(TelegramPresentation):
    query_article: InlineQueryResultArticle


@dataclass
class TelegramCountryPres(TelegramPresentation): ...


@dataclass
class TelegramInlineResultListPres:
    results: list[InlineQueryResultArticle]
    button: Optional[InlineQueryResultsButton]


class ITelegramPresenter(ABC):
    """Builds Telegram API objects from domain view models.

    This is the inversion boundary: domain/services speak in view models,
    the presenter translates them into Telegram API objects.
    Mock this interface to test handlers without Telegram API objects.
    """

    @abstractmethod
    def make_inline_query_presentation(
        self,
        result: GameSearchResult,
    ) -> "TelegramInlineResultListPres": ...

    @abstractmethod
    def make_error_presentation(
        self, error: "SpecialResults"
    ) -> "TelegramInlineResultListPres": ...

    @abstractmethod
    def make_delete_confirmation(self, success: bool) -> "TelegramPresentation": ...

    def make_currency_message_from_country(
        self,
        country_mod: Optional[CountryModification],
        alternative_suggestions: list[str],
    ) -> TelegramCountryPres: ...


def MakeSetCurrencyCallback(country_code: str) -> str:
    return f"setcurrency {country_code}"


# TODO add support to multiple deals
def _gameresult_to_gameresultvm(game: core.SourcedGame) -> GameResultVM:
    # TODO see what code will be responsible for price formatting
    deal = game.deals[0] if game.deals else None
    price = (
        None
        if deal is None
        else f"{deal.value_minor} {deal.currency_3l} ({deal.country_l2})"
    )

    if game.proton_db_info:
        proton_vm = ProtonDBVM(
            tier=game.proton_db_info.tier,
            positive_trend=False,
            total_reports=game.proton_db_info.total,
            appid=game.external_id,
        )
    else:
        proton_vm = None

    return GameResultVM(
        id=game.game.id,
        link=game.url,
        title=game.game.title,
        appid=game.external_id,
        price=price,
        is_free=deal.full_value_minor == 0 if deal is not None else False,
        discount=deal.discount if deal is not None else None,
        proton_db=proton_vm,
    )


class TelegramPresenter(ITelegramPresenter):
    """Concrete implementation: builds real Telegram API objects."""

    def _present_proton_db_vm(self, protondb: ProtonDBVM | None) -> str:
        if not protondb:
            return ""
        tier_emoji = protondb.tier.to_emoji()

        text = (
            f"[ProtonDB Tier](https://www.protondb.com/app/{protondb.appid}): {str(protondb.tier)}"
            f" {'📈' if protondb.positive_trend else '📉'}"
            f"{tier_emoji}"
            f"\t({protondb.total_reports} reports)"
        )
        return text

    def _game_price_line(self, game: GameResultVM) -> str:
        price = (
            "Price: FREE"
            if game.is_free
            else f"Price: {game.price}"
            if game.price is not None
            else "Not purchasable"
        )
        return price

    def _present_game_result_vm(self, game: GameResultVM) -> str:
        price = self._game_price_line(game)
        discount = f"\t\\[-{game.discount}%]" if game.discount is not None else ""

        return (
            f"[{game.title}]({game.link})"
            + "\n"
            + price
            + discount
            + "\n"
            + self._present_proton_db_vm(game.proton_db)
        )

    def _make_inline_game_article(
        self, game: GameResultVM, country_config: CountryConfig
    ) -> TelegramInlineArticlePres:
        keyboard_markup = self._make_keyboard_markup(
            appid=game.appid,
            steam_link=game.link,
            has_proton_db=game.proton_db is not None,
        )

        message_text = self._present_game_result_vm(game)

        # this must be refactored asap.
        # at this point it's soldered rather than coupled
        query_result = InlineQueryResultArticle(
            id=str(uuid4()),
            title=game.title,
            description=self._game_price_line(game),
            thumbnail_url=(
                f"https://cdn.akamai.steamstatic.com/steam/apps/"
                f"{game.appid}/capsule_sm_120.jpg?t"
            ),
            input_message_content=InputTextMessageContent(
                parse_mode="Markdown",
                message_text=message_text,
            ),
            reply_markup=keyboard_markup,
        )

        return TelegramInlineArticlePres(
            query_article=query_result,
            text=message_text,
            keyboard=keyboard_markup,
            parse_mode="Markdown",
        )

    def _make_special_inline_query_result(
        self, result: SpecialResults
    ) -> InlineQueryResultArticle:
        match result:
            case SpecialResults.ERROR:
                return _make_error_result()
            case SpecialResults.QUERY_TOO_SHORT:
                return _make_too_short_result()
            case SpecialResults.NO_MATCHES:
                return _make_no_matches_result()

    def _make_inline_query_results_list(
        self,
        result: GameSearchResult,
    ) -> TelegramInlineResultListPres:
        articles = []
        for game in result.search_results:
            game_vm = _gameresult_to_gameresultvm(game)
            article = self._make_inline_game_article(
                game_vm, result.country_config
            ).query_article
            articles.append(article)

        if not articles:
            articles.append(
                self._make_special_inline_query_result(SpecialResults.NO_MATCHES)
            )

        button = (
            _make_change_currency_button()
            if not result.country_config.has_configured
            else None
        )
        return TelegramInlineResultListPres(
            button=button,
            results=articles,
        )

    def make_inline_query_presentation(
        self,
        result: GameSearchResult,
    ) -> TelegramInlineResultListPres:
        return self._make_inline_query_results_list(result)

    def make_error_presentation(
        self, error: SpecialResults
    ) -> TelegramInlineResultListPres:
        article = self._make_special_inline_query_result(error)
        return TelegramInlineResultListPres(results=[article], button=None)

    def make_delete_confirmation(self, success: bool) -> TelegramPresentation:
        if success:
            text = "Your data has been deleted 🫡"
        else:
            text = "Failed to delete your data. Please report with /report"

        return TelegramPresentation(
            text=text, keyboard=InlineKeyboardMarkup([]), parse_mode="Markdown"
        )

    def _make_country_keyboard(self, codes: list[str]) -> InlineKeyboardMarkup:
        keyboard: list[list[InlineKeyboardButton]] = []
        for i in range(0, len(codes), 3):
            row = [
                InlineKeyboardButton(code, callback_data=MakeSetCurrencyCallback(code))
                for code in codes[i : i + 3]
            ]
            keyboard.append(row)
        return InlineKeyboardMarkup(keyboard)

    def make_currency_message_from_country(
        self,
        country_mod: Optional[CountryModification],
        alternative_suggestions: list[str],
    ) -> TelegramCountryPres:

        if country_mod:
            if country_mod.configured_country:
                text = (
                    f"Your currency has been set to {country_mod.configured_country}✅"
                )
                kb = InlineKeyboardMarkup([])
            else:
                text = (
                    f"Could not set currency to *{country_mod.requested_country}*. Is it a valid country code?"
                    "\nPerhaps you meant one of those:"
                )
                kb = self._make_country_keyboard(alternative_suggestions)
        else:
            text = (
                "**How to set your currency:**\n"
                "Use `/setcurrency CODE` (e.g., `/setcurrency US`).\n\n"
                "Select one of the popular options below:"
            )
            kb = self._make_country_keyboard(alternative_suggestions)

        return TelegramCountryPres(text=text, keyboard=kb, parse_mode="Markdown")

    def _make_keyboard_markup(
        self, appid: str, steam_link: str, has_proton_db: bool
    ) -> InlineKeyboardMarkup:
        row1_buttons = [InlineKeyboardButton("Steam Page", url=steam_link)]

        if has_proton_db:
            row1_buttons.append(
                InlineKeyboardButton(
                    "ProtonDB 🐧", url=f"https://www.protondb.com/app/{appid}"
                )
            )

        row2_buttons = [
            InlineKeyboardButton(
                "Price History", url=f"https://steamdb.info/app/{appid}/#pricehistory"
            )
        ]

        return InlineKeyboardMarkup([row1_buttons, row2_buttons])


def _make_change_currency_button() -> InlineQueryResultsButton:
    return InlineQueryResultsButton(
        text="Change currency / hide this", start_parameter="setcurrency"
    )


def _make_error_result() -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=str(uuid4()),
        title="Error",
        description=(
            "Error: Sorry. Please report this with the /report command so we can fix it."
        ),
        input_message_content=InputTextMessageContent(
            parse_mode="Markdown",
            message_text=(
                "Error: Something has gone wrong here. Please report this with the /report command so I can fix it."
            ),
        ),
    )


def _make_too_short_result() -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=str(uuid4()),
        title="Query Too Short",
        description="Please enter more characters to search.",
        input_message_content=InputTextMessageContent(
            parse_mode="Markdown",
            message_text="Your search query is too short. Please enter more characters.",
        ),
    )


def _make_no_matches_result() -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=str(uuid4()),
        title="No Matches Found",
        description="No games matched your search.",
        input_message_content=InputTextMessageContent(
            parse_mode="Markdown",
            message_text="No games matched your search. Try a different query.",
        ),
    )
