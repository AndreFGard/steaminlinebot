from enum import IntEnum

import pydantic


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

    def to_emoji(self):
        return {
            "GOLD": "✔️(4/5)",
            "SILVER": "✔️(3/5)",
            "BRONZE": "🟡(2/5)",
            "PLATINUM": "✅(5/5)",
            "BORKED": "❌ (1/5)",
        }[self.name]

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
