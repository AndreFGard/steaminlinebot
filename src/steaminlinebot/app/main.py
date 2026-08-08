#!/usr/bin/env python3
# This program is dedicated to the public domain under the GPL3 license.

"""
@Steaminlinebot written by Andrefgard on github
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

from steaminlinebot.database.GameResultRepositoryV2 import GameResultRepositoryV2
from steaminlinebot.database.UserRepositoryV2 import UserRepositoryV2
from steaminlinebot.telegram.Bot import Bot
from steaminlinebot.telegram.TelegramPresenter import TelegramPresenter
from steaminlinebot.database import init_db
from steaminlinebot.integration.ProtonDBClient import ProtonDBClient
from steaminlinebot.game.GameSearchUsecase import GameSearchUsecase
from steaminlinebot.game.SteamProvider import SteamProvider
from steaminlinebot.integration.SteamClient import SteamClient, SteamRequestMaker
from steaminlinebot.user.UserCountry import UserCountry
from steaminlinebot.user.UserCountryUsecase import UserCountryUsecase

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
    return await update.message.reply_text(  # type: ignore
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

    game_result_repo = GameResultRepositoryV2(db)
    protondb_client = ProtonDBClient()

    steam_client = SteamClient(
        max_results=6,
        steam_request_maker=SteamRequestMaker(),
        protondb_client=protondb_client,
    )

    user_repo = UserRepositoryV2(db)
    user_country = UserCountry(user_repo=user_repo)
    search_games = SteamProvider(
        client=steam_client,
        game_result_repo=game_result_repo,
    )
    presenter = TelegramPresenter()
    game_searcher = GameSearchUsecase(
        user_country=user_country,
        search_games=search_games,
        default_country_code="US",
    )

    user_country_usecase = UserCountryUsecase(user_country=user_country)
    bot = Bot(
        user_country_usecase=user_country_usecase,
        presenter=presenter,
        game_searcher=game_searcher,
    )

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", help))
    application.add_handler(CommandHandler("help", help))

    application.add_handler(InlineQueryHandler(bot.handle_inline_query))

    application.add_handler(CommandHandler("setcurrency", bot.set_currency))
    application.add_handler(CommandHandler("deleteinfo", bot.delete_user_info))
    application.add_handler(CallbackQueryHandler(bot.callback_handler))

    application.add_error_handler(error)  # type: ignore

    application.run_polling()


if __name__ == "__main__":
    main()
