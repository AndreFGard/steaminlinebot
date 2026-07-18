from collections import defaultdict
from dataclasses import dataclass
from os import replace
from typing import Optional
from uuid import uuid4

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResult,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
)

from steaminlinebot.game.GameResult import GameResult
from steaminlinebot.game.SteamProvider import (
    GameResultVM,
    ProtonDBVM,
    SearchResults,
    SpecialResults,
)
from steaminlinebot.user.UserCountry import CountryConfig, CountryModification


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


class TelegramCallbackBuilder:
    @staticmethod
    def set_currency(country_code):
        return f"setcurrency {country_code}"


class TelegramPresenter:
    @staticmethod
    def _present_proton_db_vm(protondb: ProtonDBVM | None):
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

    @staticmethod
    def _game_price_line(game: GameResultVM):
        price = (
            "Price: FREE"
            if game.is_free
            else f"Price: {game.price}" if game.price is not None else "Not purchasable"
        )
        return price

    @staticmethod
    def _present_game_result_vm(game: GameResultVM):
        price = TelegramPresenter._game_price_line(game)
        discount = f"\t\\[-{game.discount}%]" if game.discount is not None else ""

        return (
            f"[{game.title}]({game.link})"
            + "\n"
            + price
            + discount
            + "\n"
            + TelegramPresenter._present_proton_db_vm(game.proton_db)
        )

    @staticmethod
    def _make_inline_game_article(game: GameResultVM, country_config: CountryConfig):
        keyboard_markup = TelegramPresenter._make_keyboard_markup(
            appid=game.appid,
            steam_link=game.link,
            has_proton_db=game.proton_db is not None,
        )

        message_text = TelegramPresenter._present_game_result_vm(game)

        # this must be refactored asap.
        # at this point it's soldered rather than coupled
        query_result = InlineQueryResultArticle(
            id=str(uuid4()),
            title=game.title,
            description=TelegramPresenter._game_price_line(game),
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

    @staticmethod
    def _make_special_inline_query_result(
        result: SpecialResults,
    ) -> InlineQueryResultArticle:
        match result:
            case SpecialResults.ERROR:
                return MakeErrorResult()
            case SpecialResults.QUERY_TOO_SHORT:
                return MakeTooShortResult()
            case SpecialResults.NO_MATCHES:
                return MakeNoMatchesResult()

    @staticmethod
    def _make_inline_query_results_list(
        games: SearchResults, country_config: CountryConfig
    ):
        articles = [
            TelegramPresenter._make_inline_game_article(
                game, country_config
            ).query_article
            for game in games.results
        ]
        articles.extend(
            TelegramPresenter._make_special_inline_query_result(r)
            for r in games.special_results
        )
        button = None if not country_config.has_configured else MakeChangeCurrencyButton()
        return TelegramInlineResultListPres(
            button=button,
            results=articles,
        )

    @staticmethod
    def make_inline_query_presentation(
        search_results: SearchResults, country_config: CountryConfig
    ) -> TelegramInlineResultListPres:
        return TelegramPresenter._make_inline_query_results_list(
            search_results, country_config
        )

    @staticmethod
    def make_delete_confirmation(success: bool) -> TelegramPresentation:
        if success:
            text = "Your data has been deleted 🫡"
        else:
            text = "Failed to delete your data. Please report with /report"

        return TelegramPresentation(
            text=text, keyboard=InlineKeyboardMarkup([]), parse_mode="Markdown"
        )

    @staticmethod
    def _make_country_keyboard(codes: list[str]):
        keyboard = []
        for i in range(0, len(codes), 3):
            row = [
                InlineKeyboardButton(
                    code, callback_data=TelegramCallbackBuilder.set_currency(code)
                )
                for code in codes[i : i + 3]
            ]
            keyboard.append(row)
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def make_currency_message_from_country(country_mod: CountryModification):
        if country_mod.configured_country or country_mod.requested_country:
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
                kb = TelegramPresenter._make_country_keyboard(
                    country_mod.alternative_suggestions
                )
        else:
            text = (
                "**How to set your currency:**\n"
                "Use `/setcurrency CODE` (e.g., `/setcurrency US`).\n\n"
                "Select one of the popular options below:"
            )
            kb = TelegramPresenter._make_country_keyboard(
                country_mod.alternative_suggestions
            )

        return TelegramCountryPres(text=text, keyboard=kb, parse_mode="Markdown")

    @staticmethod
    def _make_keyboard_markup(appid, steam_link, has_proton_db: bool):
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


def MakeChangeCurrencyButton():
    return InlineQueryResultsButton(
        text="Change currency / hide this", start_parameter="setcurrency"
    )


def MakeErrorResult():
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


def MakeTooShortResult():
    return InlineQueryResultArticle(
        id=str(uuid4()),
        title="Query Too Short",
        description="Please enter more characters to search.",
        input_message_content=InputTextMessageContent(
            parse_mode="Markdown",
            message_text="Your search query is too short. Please enter more characters.",
        ),
    )


def MakeNoMatchesResult():
    return InlineQueryResultArticle(
        id=str(uuid4()),
        title="No Matches Found",
        description="No games matched your search.",
        input_message_content=InputTextMessageContent(
            parse_mode="Markdown",
            message_text="No games matched your search. Try a different query.",
        ),
    )
