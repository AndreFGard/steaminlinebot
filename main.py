#!/usr/bin/env python3
# This program is dedicated to the public domain under the GPL3 license.

"""
@Steaminlinebot written by GuaximFsg (now AndreFGard) on github
"""

from functools import cache
import os
import sys
from logging import basicConfig, WARNING, INFO, DEBUG
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CallbackQueryHandler, Updater, InlineQueryHandler, CommandHandler,Application
from telegram import InlineQueryResultArticle, InputTextMessageContent
import sqlite3
import time
import dotenv

from modules.db import init_db
from modules.GameResult import GameResult
from modules.TelegramQueryMaker import (
    TelegramInlineQueryMaker,
    ERROR_RESULT,
    TOO_SHORT_RESULT,
    NO_MATCHES_RESULT,
)
from modules.SteamSearcher import SteamSearcher
from modules.Bot import Bot


dotenv.load_dotenv()
logLevel = {""}
botname = os.environ.get("BOTNAME") or "@SteamInlineBot"
basicConfig(
    level={"WARNING": WARNING, "INFO": INFO, "DEBUG": DEBUG, None: WARNING}[
        os.environ.get("LOG_LEVEL")
    ],
    format="[%(levelname)s] %(asctime)s  %(name)s: %(message)s",
)


if not os.path.exists("./data"):
    logging.warning("Creating data directory")
    os.mkdir("./data")



async def help(update: Update, context):
    return await update.message.reply_text(  # type:ignore
        f"To search with this bot, type {botname} and then something "
        f"you want to search in the message box. for example:\n"
        f"{botname} Skyrim\n"
        f"or\n"
        f"{botname} Stardew Valley\n\n"
        "\nCurrency config:\n"
        "- /setcurrency COUNTRY_CODE\n"
        "EXAMPLE: /setcurrency US",
        "\n\n Use /deleteinfo to delete your currency and userid from the system"
    )



def error(update: Update, context):
    print(f"Update {update} caused error {context.error}")


def main():
    try:
        token = os.environ["BOT_TOKEN"]
    except KeyError:
        print("No BOT_TOKEN environment variable passed. Terminating.")
        sys.exit(1)

    db = init_db.init_db("data/db.sqlite")
    bot = Bot(db)

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", help))
    application.add_handler(CommandHandler("help", help))

    application.add_handler(InlineQueryHandler(bot.handleInlineQuery))

    application.add_handler(CommandHandler("setcurrency", bot.set_currency))
    application.add_handler(CommandHandler("deleteinfo", bot.delete_user_info))
    application.add_handler(CallbackQueryHandler(bot.callback_handler))



    application.add_error_handler(error)  # type:ignore

    application.run_polling()


if __name__ == "__main__":
    main()
