import importlib.util
from pathlib import Path

from fastapi import HTTPException

from app.operations.sql_executor import execute_read_only_sql
from app.operations.ap_invoice_text_to_sql import build_ap_invoice_fetch_sql
from app.schema.response import APInvoiceActionResponse


def _load_fetch_checker():
    checker_path = Path(__file__).with_name("fetch_checker.py")
    spec = importlib.util.spec_from_file_location("ap_invoice_fetch_checker", checker_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load fetch checker from {checker_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute(intent, repository) -> APInvoiceActionResponse:
    del repository

    fetch_query = intent.fetchQuery or ""
    fetch_decision = _load_fetch_checker().decide(fetch_query)

    try:
        query_spec = build_ap_invoice_fetch_sql(
            fetch_query=fetch_query,
            intent_card_code=intent.cardCode,
            intent_doc_entry=intent.docEntry,
        )
        rows = execute_read_only_sql(query_spec["sql"], query_spec["params"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fetch execution failed: {str(exc)}") from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No AP invoices matched the fetch query")

    doc_entry = rows[0].get("doc_entry")
    count = len(rows)
    filters = query_spec["filters"]

    if count == 1:
        message = "✅ Here is the AP Invoice you requested."
    else:
        message = f"✅ I found {count} AP invoices matching your criteria."

    return APInvoiceActionResponse(
        status="fetched",
        message=message,
        docEntry=doc_entry,
        data={
            "fetchRouting": {
                "subagent": fetch_decision.subagent,
                "reason": fetch_decision.reason,
                "conditions": fetch_decision.conditions,
            },
            "filters": filters,
            "rowCount": count,
            "sql": query_spec["sql"],
            "rows": rows,
        },
    )
