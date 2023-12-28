[comment]: <> (Readme from jhenrique)
Steam Game Search Telegram Bot

## Description
1. [Development](#development)
2. [Usage](#usage)
This Telegram bot allows users to search for games on Steam and get information such as current price, price history and links to the game's Steam page and ProtonDB page. It utilizes the steam appdetails API and steam scraping to get the results.

Features

    Search for games on Steam.
    Get the current price of the game.
    Link to the game's Is There Any Deal Yet page, which provides information such as it's price history
    Links to Steam and ProtonDB for other details and linux compatibility

## Development
Requirements

    Python 3
    Telegram Bot Token, steam key and is there any deal yet key (not used)
    Libraries: requests, beautifulsoup4, python-telegram-bot, gazpacho

Setup

    Install the required Python packages:

    pip install -r requirements.txt


Set up a Telegram bot via BotFather on Telegram and get a bot token.

    export BOT_TOKEN='your_telegram_bot_token'

You can also create a .env file and put BOT_TOKEN inside it.

Usage

Run the bot locally with the following command:

    python main.py
Or, if you created the env file:
    
    env $(cat .env) python main.py   

## Usage
In Telegram, use the bot's username followed by the game title to initiate a search. For example:

    @YourBotUsername Skyrim

Contributing

Contributions, issues, and feature requests are welcome. Feel free to check issues page if you want to contribute.
License

GPL-3.0 License

Contact

    Inspired by the @archewikibot
    Created by AndreFGard on Github
    Readme by jhenrique04 on Github
<--!>