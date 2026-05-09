import json
import logging
import urllib.parse
from typing import Any

import requests

logger = logging.getLogger(__name__)


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

    encoded_query = urllib.parse.quote(normalized)
    url = f"http://vzone.in:1662/api/GetMethod/GetData?query={encoded_query}"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # The API might return a list of dicts directly or wrap it in a response object.
        # Assuming it returns a list of rows as dicts:
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Check for common wrapper structures
            for key in ["data", "result", "results", "value"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
        else:
            return []
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to execute HANA query on vzone.in: {e}")
        raise ValueError(f"HANA Database execution failed: {str(e)}") from e
