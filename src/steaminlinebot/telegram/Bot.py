import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Mapping

from telegram import Update
from telegram.ext import InvalidCallbackData

from steaminlinebot.telegram.TelegramPresenter import ITelegramPresenter
from steaminlinebot.game.SteamProvider import ISearchGames
from steaminlinebot.user.UserCountry import IUserCountry


class Bot:
    """Telegram protocol handler.

    Extracts parameters from PTB Update objects, delegates to domain
    services, then asks the presenter to build Telegram API response
    objects.  Zero knowledge of repositories or SQL.
    """

    DEFAULT_COUNTRY_CODE = "US"

    def __init__(
        self,
        search_games: ISearchGames,
        user_country: IUserCountry,
        presenter: ITelegramPresenter,
    ):
        self.search_games = search_games
        self.user_country = user_country
        self.presenter = presenter
        self._callback_handlers: Mapping[
            str, Callable[[Update, Any], Coroutine[Any, Any, Any]]
        ] = self._init_callback_handlers()

    async def handle_inline_query(self, update: Update, context):
        assert update.inline_query
        query = update.inline_query.query
        logging.warning(update)
        start = time.time()

        user_id = update.inline_query.from_user.id
        fallback_languages = [update.inline_query.from_user.language_code, "en-us"]
        country_config = self.user_country.get_country(user_id, fallback_languages)
        
        search_results = await self.search_games.search_game(
            query, country_code=country_config.country or self.DEFAULT_COUNTRY_CODE
        )

        presentation = self.presenter.make_inline_query_presentation(
            search_results, country_config
        )
        await update.inline_query.answer(
            presentation.results, cache_time=30, button=presentation.button
        )

        end_time = time.time()
        logging.info(f"RESULTS : {search_results.results}")
        print(
            f"LOG: scrape time: {search_results.scrape_time:.4f}s, total_time: {(end_time - start):.4f}s"
        )

    async def delete_user_info(self, update: Update, context):
        msg = update.message
        assert msg and msg.from_user
        user_id = msg.from_user.id

        success = self.user_country.delete_user(user_id)
        presentation = self.presenter.make_delete_confirmation(success)

        await msg.reply_text(presentation.text, parse_mode=presentation.parse_mode)

    async def set_currency(self, update: Update, context):
        """/setcurrency command, sending a keyboard, not callback"""
        message = update.message
        assert message and message.from_user
        user_id = message.from_user.id
        user_lang = message.from_user.language_code or "en-us"
        args = context.args

        country_mod = await self.user_country.parse_set_currency_command(
            args, user_id, user_lang
        )
        presentation = self.presenter.make_currency_message_from_country(country_mod)

        await message.reply_text(
            presentation.text,
            parse_mode=presentation.parse_mode,
            reply_markup=presentation.keyboard,
        )

    def _init_callback_handlers(self):
        handlers = {
            "setcurrency": self._handle_currency_callback,
        }
        self._callback_handlers = handlers
        return self._callback_handlers

    async def callback_handler(self, update: Update, context):
        query = update.callback_query
        if query and not isinstance(query, InvalidCallbackData):
            # starts telegram loading animation
            await query.answer()
            # fail silently
            key = query.data.split(" ")[0] if query.data else "No callback data"

            # todo: handle errors here
            return await asyncio.gather(
                self._callback_handlers[key](update, context), query.answer()
            )

    async def _handle_currency_callback(self, update: Update, context):
        query = update.callback_query
        if not query or isinstance(query, InvalidCallbackData):
            return

        assert query.data
        user_id = query.from_user.id
        user_lang = query.from_user.language_code or "en-us"

        args = None
        if query.data.startswith("setcurrency "):
            country_code = query.data.split(" ")[1]
            args = [country_code]

        country_mod = await self.user_country.parse_set_currency_command(
            args, user_id, user_lang
        )

        presentation = self.presenter.make_currency_message_from_country(country_mod)

        await query.edit_message_text(
            presentation.text, parse_mode=presentation.parse_mode
        )
        if presentation.keyboard.inline_keyboard:
            await query.edit_message_reply_markup(presentation.keyboard)
