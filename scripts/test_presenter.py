"""Manual test script for telegram_presenter using a fixture JSON file."""

import json
from pathlib import Path

from steaminlinebot.game.core import SourcedGame
from steaminlinebot.game.game_search_usecase import GameSearchResult
from steaminlinebot.telegram.telegram_presenter import TelegramPresenter
from steaminlinebot.user.user_country import CountryConfig

root = Path(__file__).resolve().parent.parent


FIXTURE_PATH = root / "data" / "fixtures" / "game_search_result_fixture.json"


def load_fixture(path: Path) -> GameSearchResult:
    raw = json.loads(path.read_text())

    search_results = []
    for item in raw["search_results"]:
        game = SourcedGame.model_validate(item)
        search_results.append(game)

    country_cfg = CountryConfig(
        country=raw["country_config"]["country"],
        has_configured=raw["country_config"]["has_configured"],
    )

    return GameSearchResult(
        search_results=search_results,
        country_config=country_cfg,
    )


def main():
    result = load_fixture(FIXTURE_PATH)
    presenter = TelegramPresenter()
    presentation = presenter.make_inline_query_presentation(result)

    for article in presentation.results:
        print("Title:".center(80, "=") + f"\n{article.title}")
        print("Description:".center(80, "=") + f"\n{article.description}")
        print(
            "Message Text: ".center(80, "=")
            + f"\n{article.input_message_content.message_text}"  # type: ignore[reportAttributeAccessIssue]
        )
        print()


if __name__ == "__main__":
    main()
