"""Configuration package for VIMC Manifest Cleaner."""

from config.constants import (
    APP_TITLE,
    APP_VERSION,
    APP_AUTHOR_VI,
    APP_AUTHOR_EN,
    UI_TEXT,
    COLORS,
    SHIP_TYPES,
    SHIP_KEYWORDS,
    OUTPUT_COLUMNS,
    OUTPUT_COLUMN_MAPPING,
)

from config.mappings import (
    SIZE_TO_ISO,
    CARGO_TYPE_MAPPING,
)

__all__ = [
    "APP_TITLE",
    "APP_VERSION",
    "APP_AUTHOR_VI",
    "APP_AUTHOR_EN",
    "UI_TEXT",
    "COLORS",
    "SHIP_TYPES",
    "SHIP_KEYWORDS",
    "OUTPUT_COLUMNS",
    "OUTPUT_COLUMN_MAPPING",
    "SIZE_TO_ISO",
    "CARGO_TYPE_MAPPING",
]
