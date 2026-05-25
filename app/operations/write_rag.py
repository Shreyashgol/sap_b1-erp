import json
from typing import Any

from app.config import PURCHASE_TEAM_CLAUDE_API_KEY, PURCHASE_TEAM_CLAUDE_MODEL
from app.operations.claude_client import claude_chat_completion


def _extract_sql(text: str) -> str:
    cleaned = text.strip()
    if "```" in cleaned:
        for block in cleaned.split("```"):
            if "INSERT" in block.upper() or "UPDATE" in block.upper() or "DELETE" in block.upper():
                block = block.strip().lstrip("sql").lstrip("hana").strip()
                return block.rstrip(";").strip()
    return cleaned.replace("\n", " ").strip().rstrip(";")


def generate_write_sql(document_type: str, action: str, payload: dict[str, Any]) -> str:
    """
    Generates a dummy HANA SQL statement representing the write operation.
    This is purely for UI visualization and is NOT executed against the database.
    """
    system = """You are an SAP HANA SQL generator.
Your task is to generate a single, valid SAP HANA SQL statement (INSERT, UPDATE, or DELETE) that represents the provided JSON payload for an SAP Business One document.

STRICT OUTPUT RULES:
- Return ONLY the raw SQL query. No markdown, no comments, no explanations.
- ALWAYS use double quotes for actual SAP Business One column names and match their exact case (e.g., "DocEntry", "DocNum", "CardCode", "ItemCode", "Quantity", "DocStatus", "CANCELED").
- Format values appropriately (strings in single quotes, numbers unquoted).
- Do not use semicolons.

TABLE MAPPING:
- purchase_order: Header table "OPOR", Row table "POR1"
- ap_invoice: Header table "OPCH", Row table "PCH1"
- purchase_return: Header table "ORPD", Row table "RPD1"

ACTION MAPPING:
- create: Generate an INSERT INTO statement for the header table, optionally followed by INSERT INTO for the row table if items are present. If multiple statements are needed, separate them with a space.
- update: Generate an UPDATE statement for the header table.
- cancel: Generate an UPDATE statement setting "CANCELED" = 'Y'.
- close: Generate an UPDATE statement setting "DocStatus" = 'C'.
"""

    user = f"""DOCUMENT TYPE: {document_type}
ACTION: {action}
PAYLOAD:
{json.dumps(payload, indent=2, default=str)}

SQL:"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    try:
        raw_sql = claude_chat_completion(
            messages,
            temperature=0,
            max_tokens=512,
            api_key=PURCHASE_TEAM_CLAUDE_API_KEY,
            model=PURCHASE_TEAM_CLAUDE_MODEL,
        )
        return _extract_sql(raw_sql)
    except Exception:
        # Fallback if LLM fails so we don't break the actual operation
        return f"-- Failed to generate SQL for {action} {document_type}"
