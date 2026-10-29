"""Shared literal search: identical Arabic/digit folding in Python and PostgreSQL."""

from sqlalchemy import func
from sqlalchemy.sql import SQLColumnExpression
from sqlalchemy.sql.elements import ColumnElement

_SOURCE = "أإآٱىة٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹"
_TARGET = "اااايه01234567890123456789"
_DROP = "ـ" + "".join(chr(code) for code in range(0x064B, 0x0653))
_TRANSLATION = str.maketrans(_SOURCE, _TARGET, _DROP)


def normalize_search_text(value: str) -> str:
    return value.translate(_TRANSLATION).lower()


def normalized_search_expression(
    value: SQLColumnExpression[str] | SQLColumnExpression[str | None],
) -> ColumnElement[str]:
    return func.lower(func.translate(value, _SOURCE + _DROP, _TARGET))
