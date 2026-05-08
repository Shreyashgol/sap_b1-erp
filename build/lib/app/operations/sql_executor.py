from datetime import date, datetime
from decimal import Decimal
import re
from typing import Any

from sqlalchemy import text

from app.config import SQL_QUERY_TIMEOUT
from app.db.base import get_db_session


FORBIDDEN_SQL_PATTERNS = (
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bcreate\b",
    r"\bgrant\b",
    r"\brevoke\b",
    r"\bcopy\b",
)

ALLOWED_TABLES = {"opor", "por1", "purchase_orders", "purchase_order_lines"}


def _validate_read_only_sql(sql: str):
    normalized = sql.strip()
    if not normalized.lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed for fetch operations")

    if ";" in normalized.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")

    lowered = normalized.lower()
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, lowered):
            raise ValueError("Unsafe SQL detected in fetch query")

    referenced_tables = set(re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", lowered))
    unknown_tables = referenced_tables - ALLOWED_TABLES
    if unknown_tables:
        raise ValueError(f"Query references unsupported tables: {', '.join(sorted(unknown_tables))}")


def _serialize_scalar(value: Any):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def execute_read_only_sql(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    _validate_read_only_sql(sql)

    with get_db_session() as session:
        timeout_ms = max(1000, int(SQL_QUERY_TIMEOUT) * 1000)
        session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
        result = session.execute(text(sql), params or {})
        rows = result.mappings().all()

    return [{key: _serialize_scalar(value) for key, value in row.items()} for row in rows]
