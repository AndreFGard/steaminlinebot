from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import uuid4

import babel
import babel.numbers
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
)

from steaminlinebot.game import core
from steaminlinebot.game.game_search_usecase import GameSearchResult
from steaminlinebot.user.user_country import CountryConfig, CountryModification


@dataclass
class GameResultStrings:
    title: str
    link: str
    appid: str
    description: str
    message_text: str
    has_proton_db: bool


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
    button: InlineQueryResultsButton | None


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
        country_mod: CountryModification | None,
        alternative_suggestions: list[str],
    ) -> CountryPresentation: ...


def make_set_currency_callback(country_code: str) -> str:
    return f"setcurrency {country_code}"


_PROTONDB_TIER_EMOJI: dict[str, str] = {
    "GOLD": "🏅(4/5)",
    "SILVER": "🥈(3/5)",
    "BRONZE": "🥈(2/5)",
    "PLATINUM": "🏅(5/5)",
    "BORKED": "❌ (1/5)",
}


def format_price(price_minor: int, currency_3l: str):
    precision = babel.numbers.get_currency_precision(currency_3l)
    value = Decimal(price_minor) / 10**precision
    return babel.numbers.format_currency(value, currency_3l)


def format_game_result(game: core.SourcedGame) -> GameResultStrings:
    """Builds all user-facing strings for a game search result."""

    historical_price_info = ""
    if game.price_overview is not None:
        historical_price_info = (
            f"Lowest price ever: "
            f"{format_price(game.price_overview.lowest_value_minor, game.price_overview.currency_3l)}"
        )

    proton_db_text = ""
    if game.proton_db_info:
        tier_emoji = _PROTONDB_TIER_EMOJI.get(game.proton_db_info.tier.name, "")
        proton_db_text = (
            f"[ProtonDB Tier](https://www.protondb.com/app/{game.external_id}): "
            f"{game.proton_db_info.tier}{tier_emoji} "
            f"{'📈' if False else '📉'}"
            f"\t({game.proton_db_info.total} reports)"
        )

    all_deals = (game.other_deals or []) + ([game.main_deal] if game.main_deal else [])
    best_deal = min(all_deals, key=lambda deal: deal.value_minor) if all_deals else None

    best_deal_str = ""
    if best_deal:
        best_deal_str = (
            f"Best price available: "
            f"[{format_price(best_deal.value_minor, best_deal.currency_3l)} "
            f"- {best_deal.source_shop}]({best_deal.url})"
        )

    # plain-text description for InlineQueryResultArticle (no markdown support)
    description = "Not purchasable"
    if game.is_free or (game.main_deal and game.main_deal.value_minor == 0):
        description = "Price: Free"
    elif game.main_deal is not None:
        description = f"Price: {format_price(game.main_deal.value_minor, game.main_deal.currency_3l)}"
        if game.main_deal.discount:
            description += f" [-{game.main_deal.discount}%]"

    # full markdown price line for input_message_content
    price_line = "Not purchasable"
    if game.is_free or (game.main_deal and game.main_deal.value_minor == 0):
        price_line = "Price: Free"
    elif game.main_deal is not None:
        price_line = f"Price: {format_price(game.main_deal.value_minor, game.main_deal.currency_3l)} "
        if game.main_deal.discount:
            price_line += f"[-{game.main_deal.discount}%] "
        if best_deal and best_deal.value_minor == game.main_deal.value_minor:
            price_line += "(Best price anywhere!)"
        elif best_deal:
            price_line += "\n" + best_deal_str

    # assemble the full message text
    message_text = (
        f"[{game.game.title}]({game.url})\n"
        + price_line
        + "\n"
        + historical_price_info
        + "\n"
        + proton_db_text
        + "\n"
    )

    return GameResultStrings(
        title=game.game.title,
        link=game.url,
        appid=game.external_id,
        description=description,
        message_text=message_text,
        has_proton_db=game.proton_db_info is not None,
    )


class TelegramPresenter(ITelegramPresenter):
    """Concrete implementation: builds real Telegram API objects."""

    def _make_inline_game_article(
        self, strings: GameResultStrings, _: CountryConfig
    ) -> TelegramInlineArticlePres:
        keyboard_markup = self._make_keyboard_markup(
            appid=strings.appid,
            steam_link=strings.link,
            has_proton_db=strings.has_proton_db,
        )

        query_result = InlineQueryResultArticle(
            id=str(uuid4()),
            title=strings.title,
            description=strings.description,
            thumbnail_url=(
                "https://cdn.akamai.steamstatic.com/steam/apps/"
                f"{strings.appid}/capsule_sm_120.jpg?t"
            ),
            input_message_content=InputTextMessageContent(
                parse_mode="Markdown",
                message_text=strings.message_text,
            ),
            reply_markup=keyboard_markup,
        )

        return TelegramInlineArticlePres(
            query_article=query_result,
            text=strings.message_text,
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
            strings = format_game_result(game)
            article = self._make_inline_game_article(
                strings, result.country_config
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
        country_mod: CountryModification | None,
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
