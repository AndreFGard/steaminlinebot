from collections import defaultdict
from sqlite3 import Connection
from types import CoroutineType
from typing import Callable,Any, Coroutine, Mapping
from modules.GameResult import GameResult
import asyncio
from modules.view.TelegramQueryMaker import (
    CHANGE_CURRENCY_BUTTON,
    TelegramPresenter,
    ERROR_RESULT,
    TOO_SHORT_RESULT,
    NO_MATCHES_RESULT,
)
from modules.SteamSearcher import SteamSearcher

import logging
import time

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import InvalidCallbackData, Updater, InlineQueryHandler, CommandHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent

from modules.db.UserRepository import UserRepository

from modules.db.GameResultRepository import GameResultRepository

class Bot:
    def __init__(self, db:Connection):
        self.queryMaker = TelegramPresenter(SteamSearcher(MAX_RESULTS=6))
        self.db = db
        self.userRepo = UserRepository(db)
        self.gameResultRepo = GameResultRepository(db)
        self._callback_handlers: Mapping[str, Callable[[Update, Any], Coroutine[Any, Any, Any]]] = self._init_callback_handlers()

    def _get_country(self, id, fallback_languages=[]):
        country = self.userRepo.get_user_country(id)
        has_set=True
        if not country:
            has_set = False
            for l in fallback_languages:
                country = self.userRepo.get_country_by_language(l)
                if country: break

        if not country: country = "US"
        return (has_set,country )

    async def handleInlineQuery(self, update: Update, context):
        query = update.inline_query.query  # type:ignore
        logging.warning(update)
        start = time.time()

        specialResults = set()
        results = []
        gameResults = []
        hasSetCountry = None

        if len(query) < 3:
            specialResults.add(TOO_SHORT_RESULT)
        else:
            try:
                hasSetCountry,country = self._get_country(
                    update.inline_query.from_user.id,#type:ignore
                    fallback_languages=[update.inline_query.from_user.language_code, "en-us"]) #type:ignore

                res = await self.queryMaker.scrapeQuery(query, country)
                gameResults = res.results

                if not gameResults:
                    specialResults.add(NO_MATCHES_RESULT)

                if res.found_error:
                    specialResults.add(ERROR_RESULT)  # type:ignore

                # telegram Inline Objects that are actually rendered after they are tap sent
                results: list[InlineQueryResultArticle] = []
                for r in gameResults:
                    try:
                        #results.append(self.queryMaker.makeInlineQueryResultArticle(r))
                        resultId = self.gameResultRepo.insert_game_result(r)
                        article,_,_ = self.queryMaker.makeInlineQueryResultArticle_interactive(r, resultId)
                        results.append(article)
                    except Exception as e:
                        print(f"LOG: ERROR: {e} WITH RESULTS: {gameResults}")
                        specialResults.add(ERROR_RESULT)
                
            except Exception as e:
                print(f"LOG: Failed to query: {e} WITH RESULTS: {gameResults}")
                specialResults.add(ERROR_RESULT)  # type:ignore

        updateTime = time.time()

        ##                                    <--------------------- magic here
        await update.inline_query.answer( #type:ignore
            results + list(specialResults),
            cache_time=30,
            button=CHANGE_CURRENCY_BUTTON if hasSetCountry == False else None
        )

        endTime = time.time()
        logging.info(f"RESULTS : {gameResults}")
        print(
            f"LOG: scrape time: {(updateTime - start):.4f}s, totalTime: {(endTime - start):.4f}s"
        )
        
    async def delete_user_info(self, update:Update, context):
        msg = update.message
        assert msg and msg.from_user
        id = msg.from_user.id
        try:
            self.userRepo.delete_user(id)
            await msg.reply_text("Your data has been deleted 🫡")
        except Exception as e:
            logging.error(f"delete user error f{e}")
            await msg.reply_text(f"Failed to delete your data. Please report with /report")


    async def set_currency(self, update: Update, context):
            """/setcurrency command, sending a keyboard, not callback"""
            message = update.message
            assert message and message.from_user
            user_id = message.from_user.id
            args = context.args 

            #well formed message (/setcurrency COUNTRY_CODE)
            if args:
                requested_country = args[0].upper()

                try:
                    success = self.userRepo.upsert_user_country(user_id, requested_country)
                except:
                    success = False

                if success:
                    await message.reply_text(f"✅ Success! Your currency has been set to {requested_country}.")
                else:
                    await message.reply_text(f"❌ Could not set currency to *{requested_country}*. Is it a valid country code?", parse_mode="Markdown")
                return

            #empty message, recommend languages
            user_lang = message.from_user.language_code or "en-us"
            local_suggestion = self.userRepo.get_country_by_language(user_lang)
            
            target_codes = ["BR", "US", "MX", "PL"]
            if local_suggestion and local_suggestion not in target_codes:
                target_codes.insert(0, local_suggestion)

            keyboard = []
            for i in range(0, len(target_codes), 3):
                row = [
                    InlineKeyboardButton(code, callback_data=f"/setcurrency {code}") 
                    for code in target_codes[i:i+3]
                ]
                keyboard.append(row)

            reply_markup = InlineKeyboardMarkup(keyboard)

            explanation = (
                "<b>How to set your currency:</b>\n"
                "Use <code>/setcurrency CODE</code> (e.g., <code>/setcurrency US</code>).\n\n"
                "Select one of the popular options below:"
            )

            await message.reply_text(
                explanation, 
                parse_mode="HTML", 
                reply_markup=reply_markup
            )
    
    def _init_callback_handlers(self):
        #this really must be refactored into an enum asap
        handlers = {
            "/setcurrency": self._handle_currency_callback,
            "protondb_cb": self._handle_game_result_callback,
            "overview_cb": self._handle_overview_callback,
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

            country_code = "(NOT SET)"
            if query.data.startswith("/setcurrency "): 
                country_code = query.data.split(" ")[1].upper()
                user_id = query.from_user.id
                
                try:
                    success = self.userRepo.upsert_user_country(user_id, country_code)
                except:
                    success = False
                query.edit_message_reply_markup
                if success:
                    return await query.edit_message_text(f"✅ Currency set to *{country_code}*.", parse_mode="Markdown")
            
            return await query.edit_message_text(f"❌ Could not set currency to '*{country_code}*'. Is it a valid country code?", parse_mode="Markdown")

    async def _handle_game_result_callback(self, update: Update, context):
        query = update.callback_query
        assert query and query.data
        
        
        if query.data.startswith("protondb_cb"):
            resultId = int(query.data.split(' ')[1])
            gameResult = self.gameResultRepo.get_game_result(resultId)
            assert gameResult
            protondb = gameResult.protonDBReport
            text,keyboardMarkup = TelegramPresenter.makeProtonDBResultText(gameResult, resultId)
            # await asyncio.gather(
            #     query.edit_message_text(text),
            #     query.edit_message_reply_markup(keyboardMarkup)
            # )

            #order seems to matter
            await query.edit_message_text(text, parse_mode="Markdown")
            await query.edit_message_reply_markup(keyboardMarkup)

    async def _handle_overview_callback(self, update:Update, context):
        query = update.callback_query
        assert query and query.data
        resultId = int(query.data.split(' ')[1])
        gameResult = self.gameResultRepo.get_game_result(resultId)
        assert gameResult
        article,text,keyboardMarkup = TelegramPresenter.makeInlineQueryResultArticle_interactive(
            gameResult, resultId
        )
        #todo: refactor asap
        await query.edit_message_text(text, parse_mode='Markdown')
        await query.edit_message_reply_markup(keyboardMarkup)

        




                


        