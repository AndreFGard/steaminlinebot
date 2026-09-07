from enum import IntEnum

import pydantic

#TODO move to enum.Enum
class ProtonDBTier(IntEnum):
    BORKED = 1
    BRONZE = 2
    SILVER = 3
    GOLD = 4
    PLATINUM = 5

    def label(self):
        return self.name.lower().capitalize()

    def __str__(self):
        return self.label()

    @classmethod
    def from_int(cls, tier: int):
        return cls(tier)


# TODO move to core?
class ProtonDBReport(pydantic.BaseModel):
    game_id: int
    best_reported_tier: ProtonDBTier
    confidence: str
    score: float
    tier: ProtonDBTier
    total: int
    """Total number of reports"""
    trending_tier: ProtonDBTier

    def __repr__(self):
        return str(self.__dict__)
