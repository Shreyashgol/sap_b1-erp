from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import (
    SALES_RAG_EMBEDDING_MODEL,
    SALES_RAG_PERSIST_DIR,
    SALES_RAG_USE_VECTOR,
    SALES_SQL_CLAUDE_API_KEY,
    SALES_SQL_CLAUDE_MODEL,
)
from app.operations.claude_client import claude_chat_completion

RAG_ROOT = Path(__file__).resolve().parents[1] / "rag"
DATA_DIR = RAG_ROOT / "data"
SALES_TABLES_PATH = DATA_DIR / "sales_tables.json"
SALES_QUERIES_PATH = DATA_DIR / "sales_queries.json"

ALLOWED_SALES_TABLES = {"ORDR", "RDR1", "OINV", "INV1", "ORDN", "RDN1", "OCRD", "OITM"}
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagDocument:
    id: str
    content: str
    embedding_text: str
    metadata: dict[str, Any]


def _load_json(path: Path):
    return json.loads(path.read_text())


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text or "")}


def _lexical_search(documents: list[RagDocument], question: str, top_k: int) -> list[dict[str, Any]]:
    query_tokens = _tokens(question)
    scored: list[tuple[float, RagDocument]] = []

    for document in documents:
        searchable_text = " ".join(
            [
                document.embedding_text,
                document.content,
                " ".join(str(value) for value in document.metadata.values()),
            ]
        )
        document_tokens = _tokens(searchable_text)
        overlap = query_tokens & document_tokens
        if not overlap:
            score = 0.0
        else:
            score = len(overlap) / max(len(query_tokens), 1)
            lower_text = searchable_text.lower()
            score += sum(0.2 for token in overlap if f" {token} " in f" {lower_text} ")

        scored.append((score, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": document.id,
            "content": document.content,
            "metadata": document.metadata,
            "score": score,
            "distance": None,
        }
        for score, document in scored[:top_k]
    ]


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _table_documents() -> list[RagDocument]:
    data = _load_json(SALES_TABLES_PATH)
    documents: list[RagDocument] = []
    for table_name, table_data in data.items():
        columns = "\n".join(f"{name}: {desc}" for name, desc in table_data.get("columns", {}).items())
        joins = "\n".join(f"{j['table']} ON {j['on']}" for j in table_data.get("joins", []))
        content = f"""Table: {table_name}
Description: {table_data.get("description", "")}
Business Meaning: {table_data.get("business_meaning", "")}
Business Terms: {", ".join(table_data.get("business_terms", []))}
Columns:
{columns}
Joins:
{joins}""".strip()
        documents.append(
            RagDocument(
                id=_stable_id("sales_schema", table_name),
                content=content,
                embedding_text=table_data.get("embedding_text", ""),
                metadata={
                    "type": "schema",
                    "table_name": table_name,
                    "embedding_text": table_data.get("embedding_text", ""),
                },
            )
        )
    return documents


def _query_documents() -> list[RagDocument]:
    data = _load_json(SALES_QUERIES_PATH)
    documents: list[RagDocument] = []
    for index, entry in enumerate(data):
        content = f"""Question: {entry.get("question", "")}
Intent: {entry.get("intent", "")}
Business Context: {entry.get("business_context", "")}
Tables Used: {", ".join(entry.get("tables_used", []))}
SQL Pattern: {entry.get("sql", "")}""".strip()
        documents.append(
            RagDocument(
                id=_stable_id("sales_query", f"{index}:{entry.get('question', '')}"),
                content=content,
                embedding_text=entry.get("embedding_text", ""),
                metadata={
                    "type": "query",
                    "intent": entry.get("intent", ""),
                    "document_type": entry.get("document_type", ""),
                    "tables_used": ",".join(entry.get("tables_used", [])),
                    "sql": entry.get("sql", ""),
                    "embedding_text": entry.get("embedding_text", ""),
                },
            )
        )
    return documents


class _EmbeddingModel:
    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(SALES_RAG_EMBEDDING_MODEL, local_files_only=True)

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [e.tolist() for e in self.model.encode(texts, normalize_embeddings=True)]


class _SalesRagStore:
    def __init__(self):
        import chromadb
        self.embedding_model = _EmbeddingModel()
        self.client = chromadb.PersistentClient(path=str(SALES_RAG_PERSIST_DIR))
        self.schema_collection = self.client.get_or_create_collection("sales_tables")
        self.query_collection = self.client.get_or_create_collection("sales_queries")
        self._ensure_indexed(self.schema_collection, _table_documents())
        self._ensure_indexed(self.query_collection, _query_documents())

    def _ensure_indexed(self, collection, documents: list[RagDocument]):
        existing_count = collection.count()
        if existing_count == len(documents):
            return
        if existing_count:
            existing = collection.get(include=[])
            ids = existing.get("ids") or []
            if ids:
                collection.delete(ids=ids)
        embeddings = self.embedding_model.encode([d.embedding_text or d.content for d in documents])
        collection.add(
            ids=[d.id for d in documents],
            documents=[d.content for d in documents],
            metadatas=[d.metadata for d in documents],
            embeddings=embeddings,
        )

    def retrieve(self, question: str, top_k_schema: int = 4, top_k_queries: int = 4) -> dict[str, list[dict]]:
        q_embed = self.embedding_model.encode([question])[0]

        def _search(col, top_k: int):
            res = col.query(query_embeddings=[q_embed], n_results=min(top_k, col.count()))
            docs = []
            if res["documents"] and res["documents"][0]:
                for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
                    docs.append({"content": doc, "metadata": meta})
            return docs

        return {
            "schema": _search(self.schema_collection, top_k_schema),
            "queries": _search(self.query_collection, top_k_queries),
        }


class _LexicalSalesRagStore:
    def __init__(self):
        self.schema_documents = _table_documents()
        self.query_documents = _query_documents()

    def retrieve(self, question: str, top_k_schema: int = 4, top_k_queries: int = 4) -> dict[str, list[dict[str, Any]]]:
        return {
            "schema": _lexical_search(self.schema_documents, question, top_k_schema),
            "queries": _lexical_search(self.query_documents, question, top_k_queries),
        }


_STORE: _SalesRagStore | _LexicalSalesRagStore | None = None


def _get_store() -> _SalesRagStore | _LexicalSalesRagStore:
    global _STORE
    if _STORE is None:
        if not SALES_RAG_USE_VECTOR:
            _STORE = _LexicalSalesRagStore()
            return _STORE
        try:
            _STORE = _SalesRagStore()
        except Exception as exc:
            logger.warning("Sales RAG vector store unavailable, using lexical retrieval: %s", exc)
            _STORE = _LexicalSalesRagStore()
    return _STORE


def _extract_sql(text: str) -> str:
    cleaned = text.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    match = re.search(r"\bselect\b.*", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if match:
        cleaned = match.group(0).strip()
    return cleaned.rstrip(";").strip()


def _referenced_tables(sql: str) -> set[str]:
    return set(re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, flags=re.IGNORECASE))


def _validate_generated_sql(sql: str):
    if not sql.lower().startswith("select"):
        raise ValueError("RAG generated a non-SELECT query")
    if ";" in sql:
        raise ValueError("RAG generated multiple SQL statements")
    unknown_tables = {table.upper() for table in _referenced_tables(sql)} - ALLOWED_SALES_TABLES
    if unknown_tables:
        raise ValueError(f"RAG generated SQL with unsupported tables: {', '.join(sorted(unknown_tables))}")


SALES_SQL_SYSTEM = """You are a SAP HANA SQL expert for SAP Business One SALES queries.

Return ONLY one valid SAP HANA SELECT query - no explanation, no markdown, no code fences.

STRICT RULES:
- Output must contain exactly one SELECT statement.
- Never generate INSERT, UPDATE, DELETE, UPSERT, MERGE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, EXECUTE, CALL, DO, GRANT, REVOKE, or transaction commands.
- Always alias tables: FROM ORDR T0, JOIN OCRD T1 ON ...
- Use alias when referencing columns: T0."DocTotal", T1."CardName"
- ALWAYS wrap EVERY column name in double quotes: T0."DocEntry" WITHOUT EXCEPTION
- Use LIMIT N for row limiting, not TOP
- Use IFNULL() not ISNULL()
- Use CURRENT_DATE for today's date
- Use COALESCE for null handling
- Never use semicolons
- Never use CTEs unless absolutely required
- Never use wildcard SELECT * unless explicitly requested.
- Only use tables: ORDR, RDR1, OINV, INV1, ORDN, RDN1, OCRD, OITM

STATUS RULES:
- "DocStatus" = 'O' means Open, 'C' means Closed
- "CANCELED" = 'Y' means Cancelled
- "CANCELED" = 'N' means Active

SAP SALES TABLES:
- Sales Orders: header=ORDR, lines=RDR1 (join on "DocEntry")
- AR Invoices:  header=OINV, lines=INV1 (join on "DocEntry")
- Sales Returns: header=ORDN, lines=RDN1 (join on "DocEntry")
- Customers: OCRD (join ORDR, OINV, or ORDN on "CardCode")
- Items:     OITM (join RDR1, INV1, or RDN1 on "ItemCode")
- AR invoices linked to a sales order: JOIN INV1 invoice lines to ORDR sales order header with INV1."BaseEntry" = ORDR."DocEntry" and INV1."BaseType" = 17, then JOIN OINV on OINV."DocEntry" = INV1."DocEntry".
- When the user says "sales order 504632", treat the number as ORDR."DocEntry" unless they explicitly say sales order number or DocNum.

BUSINESS RULES:
- Sales orders represent customer commitments and pipeline.
- AR invoices represent finalized customer billing and revenue.
- Sales returns represent returned goods or credit against customer sales.
- Join header and row tables using header."DocEntry" = row."DocEntry".
- Use ORDER BY for ranked outputs.
- Prefer LIMIT 10 for ranked/list queries unless user specifies another limit.
- Ensure all non-aggregated selected columns are included in GROUP BY.
"""


def _build_sql_prompt(question: str, retrieval: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    schema_context = "\n\n--\n\n".join(item["content"] for item in retrieval["schema"])
    query_context = "\n\n--\n\n".join(item["content"] for item in retrieval["queries"])

    context = f"""SCHEMA_DETAILS:
{schema_context if schema_context else "No schema details found"}

SIMILAR_SQL_EXAMPLES:
{query_context if query_context else "No similar examples found"}"""

    user = f"""USER_QUESTION:
{question}

SQL:"""
    return [
        {"role": "system", "content": SALES_SQL_SYSTEM, "cache": True},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": user},
            ],
        },
    ]


def build_sales_rag_fetch_sql(fetch_query: str) -> dict[str, Any]:
    question = fetch_query.strip()
    if not question:
        raise ValueError("Fetch query is empty")

    retrieval = _get_store().retrieve(question)
    raw = claude_chat_completion(
        _build_sql_prompt(question, retrieval),
        temperature=0,
        max_tokens=1024,
        timeout=60,
        api_key=SALES_SQL_CLAUDE_API_KEY,
        model=SALES_SQL_CLAUDE_MODEL,
    )
    sql = _extract_sql(raw)
    _validate_generated_sql(sql)
    return {
        "sql": sql,
        "params": {},
        "filters": {
            "resultType": "ragQuery",
            "strategy": "rag",
            "retrievedSchema": [item["metadata"].get("table_name") for item in retrieval["schema"]],
            "retrievedExamples": [item["metadata"].get("intent") for item in retrieval["queries"]],
        },
    }


def generate_sales_sql(question: str) -> str:
    return build_sales_rag_fetch_sql(question)["sql"]
