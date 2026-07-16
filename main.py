#!/usr/bin/env python3
# This program is dedicated to the public domain under the GPL3 license.

"""
@Steaminlinebot written by GuaximFsg (now AndreFGard) on github
"""

import logging
import os
import sys
from logging import DEBUG, INFO, WARNING, basicConfig


from telegram import (
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    InlineQueryHandler,
)

from modules.Bot import Bot
from modules.db import init_db
from modules.db.GameResultRepository import GameResultRepository
from modules.db.UserRepository import UserRepository
from modules.services.ProtonDBClient import ProtonDBClient
from modules.services.SearchGames import SearchGames
from modules.services.SteamClient import SteamClient
from modules.services.UserCountry import UserCountry


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
        "EXAMPLE: /setcurrency US"
        "\n\n Use /deleteinfo to delete your currency and userid from the system",
    )


async def error(update: Update, context):
    print(f"Update {update} caused error {context.error}")


def main():
    try:
        token = os.environ["BOT_TOKEN"]
    except KeyError:
        print("No BOT_TOKEN environment variable passed. Terminating.")
        sys.exit(1)

    db = init_db.init_db("data/db.sqlite")

    user_repo = UserRepository(db)
    game_result_repo = GameResultRepository(db)
    protondb_client = ProtonDBClient()
    steam_client = SteamClient(max_results=6, protondb_client=protondb_client)
    user_country = UserCountry(user_repo=user_repo)
    search_games = SearchGames(
        searcher=steam_client,
        game_result_repo=game_result_repo,
        user_repo=user_repo,
        user_country=user_country,
    )
    bot = Bot(
        user_repo=user_repo,
        game_result_repo=game_result_repo,
        search_games=search_games,
        user_country=user_country,
    )

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", help))
    application.add_handler(CommandHandler("help", help))

    application.add_handler(InlineQueryHandler(bot.handle_inline_query))

    application.add_handler(CommandHandler("setcurrency", bot.set_currency))
    application.add_handler(CommandHandler("deleteinfo", bot.delete_user_info))
    application.add_handler(CallbackQueryHandler(bot.callback_handler))

    application.add_error_handler(error)  # type:ignore

    application.run_polling()


if __name__ == "__main__":
    main()
