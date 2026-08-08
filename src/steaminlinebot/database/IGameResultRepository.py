from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.game.GameResultV2 import ScrapedSteamGame


class IGameResultRepository(ABC):
    """Data access for cached game results and ProtonDB reports."""

    @abstractmethod
    def insert_game_result(self, game: ScrapedSteamGame) -> int: ...

    @abstractmethod
    def get_game_result(self, gameresult_id: int) -> Optional[ScrapedSteamGame]: ...
