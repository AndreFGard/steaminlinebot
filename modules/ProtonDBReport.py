from dataclasses import dataclass
from enum import IntEnum


class ProtonDBTier(IntEnum):
    BORKED = 1
    BRONZE = 2
    SILVER = 3
    GOLD = 4
    PLATINUM = 5
    def __str__(self):
        return self.name.lower().capitalize()
    
    def to_emoji(self):
        return dict(
            {
                "GOLD": "✔️(4/5)",
                "SILVER": "✔️(3/5)",
                "BRONZE": "🟡(2/5)",
                "PLATINUM": "✅(5/5)",
                "BORKED": "❌ (1/5)",
            }
        )[self.name]

@dataclass
class ProtonDBReport:
    bestReportedTier: ProtonDBTier
    confidence: str
    score: float
    tier: ProtonDBTier
    total: int
    """Total number of reports"""
    trendingTier: ProtonDBTier
    def __repr__(self):
        return str(self.__dict__)

