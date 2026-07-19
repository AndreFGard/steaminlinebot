import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Mapping

from telegram import Update
from telegram.ext import CallbackContext, InvalidCallbackData

from steaminlinebot.game.GameSearchUsecase import IGameSearchUsecase, QueryTooShortError
from steaminlinebot.telegram.TelegramPresenter import ITelegramPresenter, SpecialResults
from steaminlinebot.user.UserCountryUsecase import IUserCountryUsecase


class Bot:
    """Telegram protocol handler."""

    def __init__(
        self,
        user_country_usecase: IUserCountryUsecase,
        presenter: ITelegramPresenter,
        game_searcher: IGameSearchUsecase,
    ):
        self._user_country_usecase = user_country_usecase
        self._presenter = presenter
        self._game_searcher = game_searcher
        self._callback_handlers: Mapping[
            str, Callable[[Update, Any], Coroutine[Any, Any, Any]]
        ] = self._init_callback_handlers()

    async def handle_inline_query(
        self, update: Update, context: CallbackContext[Any, Any, Any, Any]
    ):
        assert update.inline_query
        logging.warning(update)
        start = time.time()

        user_lang = update.inline_query.from_user.language_code
        if not user_lang:
            suggested_langs = await self._user_country_usecase.suggest_currencies("")
            user_lang = suggested_langs.alternative_suggestions[0]

        try:
            game_search_result = await self._game_searcher.handle_game_search(
                query=update.inline_query.query,
                user_id=update.inline_query.from_user.id,
                language_code=user_lang,
            )
            presentation = self._presenter.make_inline_query_presentation(
                game_search_result
            )
            end_time = time.time()
            logging.info(f"RESULTS : {game_search_result.search_results.results}")
            logging.info(
                f"Scrape time: {game_search_result.search_results.scrape_time:.4f}s, total_time: {(end_time - start):.4f}s"
            )
        except QueryTooShortError:
            presentation = self._presenter.make_error_presentation(
                SpecialResults.QUERY_TOO_SHORT
            )

        await update.inline_query.answer(
            presentation.results, cache_time=30, button=presentation.button
        )

    async def delete_user_info(
        self, update: Update, context: CallbackContext[Any, Any, Any, Any]
    ):
        msg = update.message
        assert msg and msg.from_user
        user_id = msg.from_user.id

        success = await self._user_country_usecase.delete_user_info(user_id)
        presentation = self._presenter.make_delete_confirmation(success)

        await msg.reply_text(presentation.text, parse_mode=presentation.parse_mode)

    async def set_currency(
        self, update: Update, context: CallbackContext[Any, Any, Any, Any]
    ):
        """/setcurrency command, sending a keyboard, not callback"""
        message = update.message
        assert message and message.from_user
        user_id = message.from_user.id

        country_mod = await self._user_country_usecase.set_currency(
            user_id,
            user_language_etf=message.from_user.language_code,
            country=context.args[0] if context.args else "",
        )
        presentation = self._presenter.make_currency_message_from_country(country_mod)

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

    async def callback_handler(
        self, update: Update, context: CallbackContext[Any, Any, Any, Any]
    ):
        query = update.callback_query
        if query and not isinstance(query, InvalidCallbackData):
            # must be called so telegram starts the loading animation.
            await query.answer()
            # fail silently
            key = query.data.split(" ")[0] if query.data else "No callback data"

            # todo: handle errors here
            return await asyncio.gather(
                self._callback_handlers[key](update, context), query.answer()
            )

    async def _handle_currency_callback(
        self, update: Update, context: CallbackContext[Any, Any, Any, Any]
    ):
        query = update.callback_query
        if not query or isinstance(query, InvalidCallbackData):
            return

        assert query.data
        user_id = query.from_user.id
        user_lang = query.from_user.language_code

        country = ""
        if len(query.data.split()) == 2:
            country = query.data.split(" ")[1]

        country_mod = await self._user_country_usecase.set_currency(
            user_id, user_lang, country
        )

        presentation = self._presenter.make_currency_message_from_country(country_mod)

        await query.edit_message_text(
            presentation.text, parse_mode=presentation.parse_mode
        )
        if presentation.keyboard.inline_keyboard:
            await query.edit_message_reply_markup(presentation.keyboard)
