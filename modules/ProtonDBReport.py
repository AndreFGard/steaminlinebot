from dataclasses import dataclass
@dataclass
class ProtonDBReport:
    bestReportedTier: str
    confidence: str
    score: float
    tier: str
    total: int
    trendingTier: str
    def __repr__(self):
        return str(self.__dict__)

