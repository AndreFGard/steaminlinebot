from collections import defaultdict
from sqlite3 import Connection
from types import CoroutineType
from typing import Callable,Any, Coroutine, Mapping
from modules.GameResult import GameResult
import asyncio
from modules.presentation.TelegramPresenter import TelegramPresenter
from modules.SteamSearcher import SteamSearcher
from modules.services.SearchGames import SearchGames
from modules.services.UserCountry import UserCountry

import logging
import time

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import InvalidCallbackData, Updater, InlineQueryHandler, CommandHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent

from modules.db.UserRepository import UserRepository

from modules.db.GameResultRepository import GameResultRepository

class Bot:
    def __init__(self, db:Connection):
        self.db = db
        self.userRepo = UserRepository(db)
        self.gameResultRepo = GameResultRepository(db)
        self.searchGames = SearchGames(db)
        self.userCountry = UserCountry(db)
        self._callback_handlers: Mapping[str, Callable[[Update, Any], Coroutine[Any, Any, Any]]] = self._init_callback_handlers()

    async def handleInlineQuery(self, update: Update, context):
        assert update.inline_query
        query = update.inline_query.query 
        logging.warning(update)
        start = time.time()
        
        user_id = update.inline_query.from_user.id 
        fallback_languages = [update.inline_query.from_user.language_code, "en-us"]
        
        countryConfig = self.userCountry.get_country(user_id, fallback_languages)
        searchResults = await self.searchGames.searchGame(user_id, query, fallback_languages)
        
        presentation = TelegramPresenter.makeInlineQueryPresentation(searchResults, countryConfig)
        await update.inline_query.answer( 
            presentation.results,
            cache_time=30,
            button=presentation.button
        )

        endTime = time.time()
        logging.info(f"RESULTS : {searchResults.results}")
        print(
            f"LOG: scrape time: {searchResults.scrapeTime:.4f}s, totalTime: {(endTime - start):.4f}s"
        )
        
    async def delete_user_info(self, update:Update, context):
        msg = update.message
        assert msg and msg.from_user
        user_id = msg.from_user.id
        
        success = self.userCountry.deleteUser(user_id)
        presentation = TelegramPresenter.makeDeleteConfirmation(success)
        
        # Send to Telegram
        await msg.reply_text(presentation.text, parse_mode=presentation.parse_mode)


    async def set_currency(self, update: Update, context):
            """/setcurrency command, sending a keyboard, not callback"""
            message = update.message
            assert message and message.from_user
            user_id = message.from_user.id
            user_lang = message.from_user.language_code or "en-us"
            args = context.args
            
            countryMod = await self.userCountry.parseSetCurrencyCommand(args, user_id, user_lang)
            presentation = TelegramPresenter.makeCurrencyMessageFromCountry(countryMod)
            
            await message.reply_text(
                presentation.text,
                parse_mode=presentation.parse_mode,
                reply_markup=presentation.keyboard
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
            await query.answer()
            #fail silently
            key = query.data.split(" ")[0] if query.data else "No callback data"

            #todo: handle errors here
            return await asyncio.gather(
                self._callback_handlers[key](update, context),
                query.answer()
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
            
            countryMod = await self.userCountry.parseSetCurrencyCommand(args, user_id, user_lang)
            
            presentation = TelegramPresenter.makeCurrencyMessageFromCountry(countryMod)
            
            await query.edit_message_text(presentation.text, parse_mode=presentation.parse_mode)
            if presentation.keyboard.inline_keyboard:  # Only update if there are buttons
                await query.edit_message_reply_markup(presentation.keyboard)



        




                


        