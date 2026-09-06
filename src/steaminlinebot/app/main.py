#!/usr/bin/env python3
# This program is dedicated to the public domain under the GPL3 license.

"""
@Steaminlinebot written by Andrefgard on github
"""

import asyncio
import logging
import os
import signal
import sys
from logging import DEBUG, INFO, WARNING, basicConfig


import aiohttp
from telegram import (
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    InlineQueryHandler,
)

from steaminlinebot.database.game_repository import GameRepository
from steaminlinebot.database.user_repository import UserRepository
from steaminlinebot.telegram.bot import Bot
from steaminlinebot.telegram.telegram_presenter import TelegramPresenter
from steaminlinebot.database import init_db
from steaminlinebot.integration.protondb_client import ProtonDBClient
from steaminlinebot.integration.itad_client import ITADClient
from steaminlinebot.game.game_search_usecase import GameSearchUsecase
from steaminlinebot.game.game_searcher_service import GameSearchService
from steaminlinebot.integration.steam_client import SteamClient
from steaminlinebot.user.user_country import UserCountry

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
    assert update.message is not None
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


async def main():
    try:
        token = os.environ["BOT_TOKEN"]
    except KeyError:
        print("No BOT_TOKEN environment variable passed. Terminating.")
        sys.exit(1)

    db = init_db.init_db("data/db.sqlite")

    game_result_repo = GameRepository(db)
    protondb_client = ProtonDBClient()

    async with aiohttp.ClientSession() as session:
        steam_client = SteamClient(
            session,
            protondb_client=protondb_client,
        )

        user_repo = UserRepository(db)
        user_country = UserCountry(user_repo=user_repo)

        STEAM_SHOP_ID = 61
        itad_key = os.environ.get("ITAD_KEY")
        assert itad_key is not None
        itad = ITADClient(itad_key, steam_shop_id=STEAM_SHOP_ID, session=session)

        search_games = GameSearchService(
            client=steam_client,
            game_repo=game_result_repo,
            itad_client=itad,
        )
        presenter = TelegramPresenter()
        game_searcher = GameSearchUsecase(
            user_country=user_country,
            search_games=search_games,
        )

        bot = Bot(
            user_country=user_country,
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

        # run_polling() is synchronous and manages its own event loop, so it can't be
        # called from inside an already-running loop.
        async with application:
            assert application.updater
            await application.updater.start_polling()
            await application.start()

            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except NotImplementedError:
                    pass

            await stop_event.wait()

            await application.updater.stop()
            await application.stop()


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
