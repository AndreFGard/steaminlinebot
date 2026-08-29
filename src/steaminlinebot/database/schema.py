import enum

import sqlalchemy as sql

metadata = sql.MetaData()


# Sources like steam, gog, itad — each has its own appid system.
game_source_table = sql.Table(
    "game_source",
    metadata,
    sql.Column("id", sql.Integer, primary_key=True, autoincrement=True),
    sql.Column("name", sql.String()),
    sql.Column("itad_shop_id", sql.String(), nullable=True, unique=True),
)

game_external_id_table = sql.Table(
    "game_external_id",
    metadata,
    sql.Column("game_id", sql.Integer, sql.ForeignKey("game.id"), primary_key=True),
    sql.Column(
        "source_id", sql.Integer, sql.ForeignKey("game_source.id"), primary_key=True
    ),
    sql.Column("external_id", sql.String()),
    sql.UniqueConstraint("source_id", "external_id", name="uq_external_id"),
)


class DBProductType(enum.Enum):
    GAME = "game"
    APPLICATION = "application"
    TOOL = "tool"
    DEMO = "demo"
    DLC = "dlc"
    MUSIC = "music"
    MOD = "mod"


game_table = sql.Table(
    "game",
    metadata,
    sql.Column("id", sql.Integer, primary_key=True, autoincrement=True),
    sql.Column("title", sql.String(), nullable=False),
    sql.Column(
        "product_type",
        sql.Enum(DBProductType),
        default=DBProductType.GAME,
        nullable=False,
    ),
)


class DealFlag_(enum.Enum):
    HISTORICAL_LOW = "H"
    NEW_HISTORICAL_LOW = "N"
    STORE_LOW = "S"


# One observation per poll per shop
cost_table = sql.Table(
    "cost",
    metadata,
    sql.Column("id", sql.Integer, primary_key=True, autoincrement=True),
    sql.Column("game_id", sql.Integer, sql.ForeignKey("game.id"), nullable=False),
    sql.Column("source_id", sql.Integer, sql.ForeignKey("game_source.id")),
    sql.Column("country_alpha2", sql.String(2), sql.ForeignKey("country.alpha2")),
    sql.Column("currency", sql.String(3), nullable=False),
    sql.Column(
        "collected_date",
        sql.DateTime(),
        comment="Date the external source says the data is from",
    ),
    sql.Column(
        "insertion_date",
        sql.DateTime(),
        comment="When this observation was inserted into our database",
    ),
    sql.Column("value_minor", sql.Integer, nullable=False),
    sql.Column("full_value_minor", sql.Integer, nullable=False),
    # percent with 4 decimals (99.99) -> 9999
    sql.Column("discount", sql.Integer, nullable=False),
    sql.Column("flag", sql.Enum(DealFlag_)),  # H / N / S, or null
    sql.Column("price_expires_at", sql.DateTime()),
    sql.Column("url", sql.String()),
    sql.UniqueConstraint(
        "game_id",
        "source_id",
        "country_alpha2",
        "insertion_date",
        name="uq_cost_observation",
    ),
    sql.Index(
        "ix_cost_game_country_inserted",
        "game_id",
        "country_alpha2",
        "insertion_date",
    ),
    sql.Column(
        "source_request_id",
        sql.Integer,
        sql.ForeignKey("source_request.id"),
        nullable=True,
    ),
)


class LowestPriceInPeriod_(enum.Enum):
    ALL = "all"
    YEAR = "y1"
    QUARTER = "m3"


# Aggregator-provided historical low prices (e.g. ITAD), NOT derived from the `cost` table.
historical_low_table = sql.Table(
    "historical_low",
    metadata,
    sql.Column("id", sql.Integer, primary_key=True,autoincrement=True),
    sql.Column("game_id", sql.Integer, sql.ForeignKey("game.id"), nullable=False),
    sql.Column(
        "country_alpha2",
        sql.String(2),
        sql.ForeignKey("country.alpha2"),
        nullable=False,
    ),
    sql.Column("scope", sql.Enum(LowestPriceInPeriod_)),
    sql.Column("currency", sql.String(3), nullable=False),
    sql.Column("lowest_value_minor", sql.Integer, nullable=False),
    # date when was collected from an external source.
    sql.Column("collected_date", sql.DateTime(), nullable=False),
)

proton_report_table = sql.Table(
    "proton_report",
    metadata,
    sql.Column("id", sql.Integer, primary_key=True),
    sql.Column("game_id", sql.Integer, sql.ForeignKey("game.id")),
    sql.Column(
        "source_id",
        sql.Integer,
        sql.ForeignKey("game_source.id"),
    ),
    sql.Column("best_reported_tier", sql.Integer),
    sql.Column("confidence", sql.String()),
    sql.Column("score", sql.Float),
    sql.Column("tier", sql.Integer, nullable=False),
    sql.Column("total", sql.Integer),
    sql.Column("trending_tier", sql.Integer),
    sql.Column("collected_date", sql.DateTime(), nullable=False),
)

# Per-poll raw cache of an upstream API response (Steam / ITAD / GOG / PROTONDB).
# Each cost observation is associated with such a request.
source_request_table = sql.Table(
    "source_request",
    metadata,
    sql.Column("id", sql.Integer, primary_key=True, autoincrement=True),
    sql.Column("platform", sql.String()),
    sql.Column("url", sql.String()),
    # nullable: some endpoints are region-agnostic
    sql.Column(
        "country_alpha2", sql.String(2), sql.ForeignKey("country.alpha2"), nullable=True
    ),
    # Date when the data was collected from an external source
    sql.Column("collected_date", sql.DateTime(), nullable=False),
    sql.Column("raw_payload", sql.JSON(), nullable=False),
)

# necessary due to callback support.
game_search_queries_table = sql.Table(
    "game_search_query",
    metadata,
    sql.Column("telegram_id", sql.Integer, primary_key=True),
    sql.Column("game_id", sql.Integer, sql.ForeignKey("game.id")),
    sql.Column("cost_id", sql.Integer, sql.ForeignKey("cost.id")),
    sql.Column("sender_user_id", sql.Integer, sql.ForeignKey("user.id")),
)

country_table = sql.Table(
    "country",
    metadata,
    sql.Column("alpha2", sql.String(2), primary_key=True),
    sql.Column("language", sql.String(10)),
)


user_table = sql.Table(
    "user",
    metadata,
    sql.Column("id", sql.Integer, primary_key=True, autoincrement=True),
    sql.Column("telegram_id", sql.Integer, unique=True, nullable=False),
    sql.Column("country_alpha2", sql.String(2), sql.ForeignKey("country.alpha2")),
)
