from __future__ import annotations

from decimal import Decimal
import re
from typing import Any


NUMERIC_OUTPUT_NAMES = {
    "doctotal",
    "doctotalfc",
    "paidtodate",
    "paidsum",
    "vatsum",
    "discsum",
    "rounddif",
    "balancedue",
    "quantity",
    "openqty",
    "opencreqty",
    "openinvqty",
    "delivrdqty",
    "price",
    "pricebefdi",
    "discprcnt",
    "linetotal",
    "currencyrate",
    "rate",
    "vatprcnt",
    "stockprice",
    "grossbuypr",
    "gtotal",
    "linevat",
    "stockvalue",
}

NON_NUMERIC_OUTPUT_NAME_PATTERNS = (
    "date",
    "time",
    "status",
    "name",
    "code",
    "description",
    "dscription",
    "comment",
    "address",
    "phone",
    "email",
)

NUMERIC_ALIAS_WORDS = (
    "amount",
    "avg",
    "average",
    "balance",
    "discount",
    "paid",
    "pending",
    "percent",
    "price",
    "quantity",
    "rate",
    "revenue",
    "spend",
    "sum",
    "tax",
    "total",
    "value",
)

WRAPPER_VALUE_KEYS = (
    "value",
    "Value",
    "VALUE",
    "amount",
    "Amount",
    "AMOUNT",
    "decimal",
    "Decimal",
    "DECIMAL",
)


def make_numeric_select_json_safe(sql: str) -> str:
    """Cast selected numeric measures to DOUBLE so HANA JSON returns numbers."""
    select_bounds = _top_level_select_bounds(sql)
    if not select_bounds:
        return sql

    select_start, from_start = select_bounds
    select_list = sql[select_start:from_start]
    items = _split_top_level(select_list)
    safe_items = [_cast_select_item_if_numeric(item) for item in items]
    return f"{sql[:select_start].rstrip()} {', '.join(safe_items)} {sql[from_start:].lstrip()}"


def normalize_result_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: _normalize_cell(value) for key, value in row.items()} for row in rows]


def _normalize_cell(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _clean_number(float(value))
    if isinstance(value, dict):
        for key in WRAPPER_VALUE_KEYS:
            if key in value and len(value) <= 2:
                return _normalize_cell(value[key])
        return {nested_key: _normalize_cell(nested_value) for nested_key, nested_value in value.items()}
    if isinstance(value, list):
        return [_normalize_cell(item) for item in value]
    return value


def _clean_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def _top_level_select_bounds(sql: str) -> tuple[int, int] | None:
    match = re.match(r"\s*select\b", sql, flags=re.IGNORECASE)
    if not match:
        return None

    start = match.end()
    depth = 0
    quote: str | None = None
    index = start
    while index < len(sql):
        char = sql[index]
        if quote:
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif depth == 0 and sql[index : index + 4].lower() == "from":
            before = sql[index - 1] if index > 0 else " "
            after = sql[index + 4] if index + 4 < len(sql) else " "
            if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                return start, index
        index += 1
    return None


def _split_top_level(select_list: str) -> list[str]:
    items: list[str] = []
    depth = 0
    quote: str | None = None
    start = 0
    for index, char in enumerate(select_list):
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif char == "," and depth == 0:
            items.append(select_list[start:index].strip())
            start = index + 1
    trailing = select_list[start:].strip()
    if trailing:
        items.append(trailing)
    return items


def _cast_select_item_if_numeric(item: str) -> str:
    expression, alias = _split_alias(item)
    clean_expression = expression.strip()
    if not clean_expression or _should_skip_expression(clean_expression):
        return item.strip()

    output_name = alias or _last_quoted_identifier(clean_expression)
    if not _looks_numeric(clean_expression, output_name):
        return item.strip()

    safe_alias = alias or output_name
    if not safe_alias:
        return item.strip()
    return f'CAST({clean_expression} AS DOUBLE) AS "{safe_alias}"'


def _split_alias(item: str) -> tuple[str, str | None]:
    match = re.search(r'\s+AS\s+"?([A-Za-z_][A-Za-z0-9_]*)"?\s*$', item, flags=re.IGNORECASE)
    if match:
        return item[: match.start()].strip(), match.group(1)
    return item.strip(), None


def _last_quoted_identifier(expression: str) -> str | None:
    matches = re.findall(r'"([^"]+)"', expression)
    return matches[-1] if matches else None


def _should_skip_expression(expression: str) -> bool:
    lowered = expression.lower().strip()
    return (
        lowered == "*"
        or lowered.endswith(".*")
        or lowered.startswith("cast(")
        or lowered.startswith("count(")
        or lowered.startswith("json_")
        or "json_" in lowered
    )


def _looks_numeric(expression: str, output_name: str | None) -> bool:
    lowered_expression = expression.lower()
    lowered_output = (output_name or "").lower()
    if lowered_output in NUMERIC_OUTPUT_NAMES:
        return True
    if _looks_non_numeric_output(lowered_expression, lowered_output):
        return False
    if lowered_output and any(word in lowered_output for word in NUMERIC_ALIAS_WORDS):
        return True
    if re.search(r"\b(sum|avg)\s*\(", lowered_expression):
        return True
    if re.search(r'"(?:' + "|".join(re.escape(name) for name in NUMERIC_OUTPUT_NAMES) + r')"', expression, flags=re.IGNORECASE):
        return True
    return bool(re.search(r'"\w+"\s*[-+*/]\s*(?:ifnull|coalesce|\w+\.)?', lowered_expression))


def _looks_non_numeric_output(lowered_expression: str, lowered_output: str) -> bool:
    if lowered_output and any(pattern in lowered_output for pattern in NON_NUMERIC_OUTPUT_NAME_PATTERNS):
        return True
    quoted_names = [name.lower() for name in re.findall(r'"([^"]+)"', lowered_expression)]
    if quoted_names and all(any(pattern in name for pattern in NON_NUMERIC_OUTPUT_NAME_PATTERNS) for name in quoted_names):
        return True
    return False
