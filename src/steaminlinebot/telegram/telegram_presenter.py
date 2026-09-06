from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

import babel
import babel.numbers
import pydantic
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
)

from steaminlinebot.game import core
from steaminlinebot.game.game_search_usecase import GameSearchResult
from steaminlinebot.game.protondb_report import ProtonDBTier
from steaminlinebot.user.user_country import CountryConfig, CountryModification


@dataclass
class ProtonDBVM:
    tier: ProtonDBTier
    positive_trend: bool
    total_reports: int
    appid: str


class GameResultVM(pydantic.BaseModel):
    """View Model"""

    id: int
    link: str
    title: str
    appid: str
    historical_price_info: str
    price_line: str
    description: str
    proton_db: Optional[ProtonDBVM]


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
class CountryPresentation(TelegramPresentation): ...


@dataclass
class InlineResultListPresentation:
    results: list[InlineQueryResultArticle]
    button: Optional[InlineQueryResultsButton]


class ITelegramPresenter(ABC):
    """Builds Telegram API objects from domain models, using a view model."""

    @abstractmethod
    def make_inline_query_presentation(
        self,
        result: GameSearchResult,
    ) -> "InlineResultListPresentation": ...

    @abstractmethod
    def make_error_presentation(
        self, error: "SpecialResults"
    ) -> "InlineResultListPresentation": ...

    @abstractmethod
    def make_delete_confirmation(self, success: bool) -> "TelegramPresentation": ...

    def make_currency_message_from_country(
        self,
        country_mod: Optional[CountryModification],
        alternative_suggestions: list[str],
    ) -> CountryPresentation: ...


def make_set_currency_callback(country_code: str) -> str:
    return f"setcurrency {country_code}"


def format_price(price_minor: int, currency_3l: str):
    precision = babel.numbers.get_currency_precision(currency_3l)
    value = Decimal(price_minor) / 10**precision
    return babel.numbers.format_currency(value, currency_3l)


# TODO add support to multiple deals
def _gameresult_to_gameresultvm(game: core.SourcedGame) -> GameResultVM:
    historical_price_info = ""
    if game.price_overview is not None:
        historical_price_info = f"Lowest price ever: {format_price(game.price_overview.lowest_value_minor, game.price_overview.currency_3l)}"

    proton_vm = None
    if game.proton_db_info:
        proton_vm = ProtonDBVM(
            tier=game.proton_db_info.tier,
            positive_trend=False,
            total_reports=game.proton_db_info.total,
            appid=game.external_id,
        )

    best_other_str = ""
    best_other = None
    if game.other_deals:
        best_other = min(game.other_deals, key=lambda deal: deal.full_value_minor)
        best_other_str = (
            f"Best price available: [{best_other.source_shop}]"
            f"({best_other.url}) {format_price(best_other.value_minor, best_other.currency_3l)}"
        )

    # plain-text description for InlineQueryResultArticle (no markdown support)
    description = "Not purchasable"
    if game.main_deal and game.main_deal.value_minor == 0:
        description = "Price: Free"
    elif game.main_deal is not None:
        description = f"Price: {format_price(game.main_deal.value_minor, game.main_deal.currency_3l)}"
        if game.main_deal.discount:
            description += f" [-{game.main_deal.discount}%]"

    # full markdown price line for input_message_content
    price_line = "Not purchasable"
    if game.main_deal and game.main_deal.value_minor == 0:
        price_line = "Price: Free"
    elif game.main_deal is not None:
        price_line = f"Price: {format_price(game.main_deal.value_minor, game.main_deal.currency_3l)} "
        if game.main_deal.discount:
            price_line += f"[-{game.main_deal.discount}%] "
        if best_other and best_other.value_minor == game.main_deal.value_minor:
            price_line += f" [{best_other.source_shop}]({best_other.url}) {format_price(best_other.value_minor, best_other.currency_3l)}"
        elif best_other:
            price_line += "\n"
            price_line += best_other_str

    return GameResultVM(
        id=game.game.id,
        link=game.url,
        title=game.game.title,
        appid=game.external_id,
        price_line=price_line,
        description=description,
        historical_price_info=historical_price_info,
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

    def _present_game_result_vm(self, game: GameResultVM) -> str:
        price = game.price_line

        return (
            f"[{game.title}]({game.link})\n"
            + price
            + "\n"
            + game.historical_price_info
            + "\n\n"
            + self._present_proton_db_vm(game.proton_db)
            + "\n"
        )

    def _make_inline_game_article(
        self, game: GameResultVM, _: CountryConfig
    ) -> TelegramInlineArticlePres:
        keyboard_markup = self._make_keyboard_markup(
            appid=game.appid,
            steam_link=game.link,
            has_proton_db=game.proton_db is not None,
        )

        message_text = self._present_game_result_vm(game)

        query_result = InlineQueryResultArticle(
            id=str(uuid4()),
            title=game.title,
            description=game.description,
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
    ) -> InlineResultListPresentation:
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
        return InlineResultListPresentation(
            button=button,
            results=articles,
        )

    def make_inline_query_presentation(
        self,
        result: GameSearchResult,
    ) -> InlineResultListPresentation:
        return self._make_inline_query_results_list(result)

    def make_error_presentation(
        self, error: SpecialResults
    ) -> InlineResultListPresentation:
        article = self._make_special_inline_query_result(error)
        return InlineResultListPresentation(results=[article], button=None)

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
                InlineKeyboardButton(
                    code, callback_data=make_set_currency_callback(code)
                )
                for code in codes[i : i + 3]
            ]
            keyboard.append(row)
        return InlineKeyboardMarkup(keyboard)

    def make_currency_message_from_country(
        self,
        country_mod: Optional[CountryModification],
        alternative_suggestions: list[str],
    ) -> CountryPresentation:

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

        return CountryPresentation(text=text, keyboard=kb, parse_mode="Markdown")

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
