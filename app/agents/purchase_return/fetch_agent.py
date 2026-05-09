import importlib.util
from pathlib import Path

from fastapi import HTTPException

from app.operations.sql_executor import execute_read_only_sql
from app.operations.purchase_return_text_to_sql import build_purchase_return_fetch_sql
from app.operations.purchase_rag import build_purchase_rag_fetch_sql, should_use_purchase_rag
from app.schema.response import PurchaseReturnActionResponse


def _load_fetch_checker():
    checker_path = Path(__file__).with_name("fetch_checker.py")
    spec = importlib.util.spec_from_file_location("purchase_return_fetch_checker", checker_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load fetch checker from {checker_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute(intent, repository) -> PurchaseReturnActionResponse:
    del repository
    fetch_query = intent.fetchQuery or ""
    fetch_decision = _load_fetch_checker().decide(fetch_query)
    use_rag = should_use_purchase_rag(fetch_query)

    try:
        query_spec = build_purchase_rag_fetch_sql(fetch_query=fetch_query)
        rows = execute_read_only_sql(query_spec["sql"], query_spec["params"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fetch execution failed: {str(exc)}") from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No purchase returns matched the fetch query")

    count = len(rows)
    return PurchaseReturnActionResponse(
        status="fetched",
        message="✅ Here is the Purchase Return you requested." if count == 1 else f"✅ I found {count} Purchase Returns matching your criteria.",
        docEntry=rows[0].get("docentry") or rows[0].get("DocEntry"),
        data={
            "fetchRouting": {
                "subagent": fetch_decision.subagent,
                "reason": fetch_decision.reason,
                "conditions": fetch_decision.conditions,
            },
            "filters": query_spec["filters"],
            "rowCount": count,
            "sql": query_spec["sql"],
            "strategy": "rag" if use_rag else "deterministic",
            "rows": rows,
        },
    )
