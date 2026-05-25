import json
import logging
import urllib.parse
from typing import Any

import requests

from app.config import (
    HANA_SQL_API_AUTH_SCHEME,
    HANA_SQL_API_HEADERS,
    HANA_SQL_API_KEY,
    HANA_SQL_API_TOKEN,
    HANA_SQL_API_URL,
    SQL_QUERY_TIMEOUT,
)

logger = logging.getLogger(__name__)


def _hana_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "sap-erp-supervisor-agent/1.0",
    }
    if HANA_SQL_API_TOKEN:
        headers["Authorization"] = f"{HANA_SQL_API_AUTH_SCHEME} {HANA_SQL_API_TOKEN}".strip()
    if HANA_SQL_API_KEY:
        headers["x-api-key"] = HANA_SQL_API_KEY
    if HANA_SQL_API_HEADERS:
        try:
            extra_headers = json.loads(HANA_SQL_API_HEADERS)
        except json.JSONDecodeError as exc:
            raise ValueError("HANA_SQL_API_HEADERS must be a valid JSON object") from exc
        if not isinstance(extra_headers, dict):
            raise ValueError("HANA_SQL_API_HEADERS must be a JSON object")
        headers.update({str(key): str(value) for key, value in extra_headers.items()})
    return headers


def _rows_from_response(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["data", "result", "results", "value", "rows"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return []


def _raise_hana_http_error(response: requests.Response):
    safe_body = response.text[:500] if response.text else ""
    response_message = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            response_message = str(body.get("message") or body.get("detail") or "")
    except requests.exceptions.JSONDecodeError:
        response_message = safe_body
    lowered_message = response_message.lower()

    if "sql syntax error" in lowered_message or "invalid column" in lowered_message or "invalid table" in lowered_message:
        raise ValueError(
            "HANA SQL API rejected the generated SELECT query. "
            f"Reason: {response_message or safe_body}"
        )

    if response.status_code == 401:
        raise ValueError(
            "HANA SQL API rejected the request with 401 Unauthorized. "
            "Set or refresh HANA_SQL_API_TOKEN / HANA_SQL_API_KEY in .env."
        )
    if response.status_code == 403:
        raise ValueError(
            "HANA SQL API rejected the request with 403 Forbidden. "
            "If this data service requires credentials, set HANA_SQL_API_TOKEN, HANA_SQL_API_KEY, or HANA_SQL_API_HEADERS in .env. "
            f"Response preview: {safe_body}"
        )
    raise ValueError(f"HANA SQL API returned HTTP {response.status_code}: {safe_body}")


def execute_read_only_sql(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """
    Executes a read-only HANA SQL query via the external vzone.in API.
    """
    # The new HANA pipeline does not support parameterized queries via this GET API.
    # The SQL should already be fully formatted by the LLM or caller.
    if params:
        logger.warning(f"execute_read_only_sql called with params {params}, but HANA GET API does not support parameterized SQL directly.")

    normalized = sql.strip()
    if not normalized.lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed for fetch operations")

    if ";" in normalized.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")

    encoded_query = urllib.parse.urlencode({"query": normalized})
    url = f"{HANA_SQL_API_URL}?{encoded_query}"

    try:
        response = requests.get(url, headers=_hana_headers(), timeout=SQL_QUERY_TIMEOUT)
        if response.status_code >= 400:
            _raise_hana_http_error(response)
        data = response.json()
        return _rows_from_response(data)
            
    except requests.exceptions.ConnectTimeout as e:
        logger.error("Timed out connecting to HANA SQL API at %s: %s", HANA_SQL_API_URL, e)
        raise ValueError(
            f"HANA SQL API connection timed out after {SQL_QUERY_TIMEOUT}s. "
            f"Check that {HANA_SQL_API_URL} is reachable from this machine/network."
        ) from e
    except requests.exceptions.JSONDecodeError as e:
        logger.error("HANA SQL API returned non-JSON response via %s: %s", HANA_SQL_API_URL, e)
        raise ValueError("HANA SQL API returned a non-JSON response. Check the data service response format.") from e
    except requests.exceptions.RequestException as e:
        logger.error("Failed to execute HANA query via %s: %s", HANA_SQL_API_URL, e)
        raise ValueError(f"HANA Database execution failed: {str(e)}") from e
