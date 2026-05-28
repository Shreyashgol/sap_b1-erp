from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from app.config import (
    PURCHASE_RAG_EMBEDDING_MODEL,
    PURCHASE_RAG_PERSIST_DIR,
    PURCHASE_TEAM_CLAUDE_API_KEY,
    PURCHASE_TEAM_CLAUDE_MODEL,
)
from app.operations.claude_client import claude_chat_completion
from app.operations.sql_numeric_safety import make_numeric_select_json_safe


RAG_ROOT = Path(__file__).resolve().parents[1] / "rag"
DATA_DIR = RAG_ROOT / "data"
TABLES_PATH = DATA_DIR / "purchase_tables.json"
QUERIES_PATH = DATA_DIR / "purchase_queries.json"

ANALYTIC_PATTERNS = (
    r"\bhow\s+many\b",
    r"\bcount\b",
    r"\btotal\b",
    r"\bsum\b",
    r"\baverage\b",
    r"\bavg\b",
    r"\btop\b",
    r"\bhighest\b",
    r"\blowest\b",
    r"\bmost\b",
    r"\bleast\b",
    r"\brank\b",
    r"\bcompare\b",
    r"\bvs\b",
    r"\bby\s+vendor\b",
    r"\bby\s+supplier\b",
    r"\bby\s+item\b",
    r"\bper\s+vendor\b",
    r"\bper\s+supplier\b",
    r"\bper\s+item\b",
    r"\bthis\s+(week|month|year)\b",
    r"\btoday\b",
    r"\byesterday\b",
    r"\boverdue\b",
    r"\baging\b",
    r"\bageing\b",
    r"\bvariance\b",
    r"\bmismatch\b",
    r"\bduplicate\b",
    r"\bpartial(?:ly)?\s+paid\b",
    r"\bpayment\s+block\b",
    r"\bblocked\b",
    r"\btax\s+code\b",
    r"\bwithout\s+(?:a\s+)?(?:po|purchase\s+order)\b",
)

ALLOWED_RAG_TABLES = {"opor", "por1", "opch", "pch1", "orpd", "rpd1"}
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagDocument:
    id: str
    content: str
    embedding_text: str
    metadata: dict[str, Any]


def should_use_purchase_rag(fetch_query: str) -> bool:
    query = (fetch_query or "").strip().lower()
    if not query:
        return False
    return any(re.search(pattern, query) for pattern in ANALYTIC_PATTERNS)


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


def _content_hash(content: str, embedding_text: str, metadata: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "content": content,
            "embedding_text": embedding_text,
            "metadata": metadata,
        },
        sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _table_documents() -> list[RagDocument]:
    data = _load_json(TABLES_PATH)
    documents: list[RagDocument] = []
    for table_name, table_data in data.items():
        columns = "\n".join(f"{name}: {desc}" for name, desc in table_data.get("columns", {}).items())
        joins = "\n".join(f"{join['table']} ON {join['on']}" for join in table_data.get("joins", []))
        content = f"""Table: {table_name}
Description: {table_data.get("description", "")}
Business Meaning: {table_data.get("business_meaning", "")}
Business Terms: {", ".join(table_data.get("business_terms", []))}
Columns:
{columns}
Joins:
{joins}""".strip()
        metadata = {
            "type": "schema",
            "table_name": table_name,
            "embedding_text": table_data.get("embedding_text", ""),
        }
        documents.append(
            RagDocument(
                id=_stable_id("schema", table_name),
                content=content,
                embedding_text=table_data.get("embedding_text", ""),
                metadata={**metadata, "content_hash": _content_hash(content, table_data.get("embedding_text", ""), metadata)},
            )
        )
    return documents


def _query_documents() -> list[RagDocument]:
    data = _load_json(QUERIES_PATH)
    documents: list[RagDocument] = []
    for index, entry in enumerate(data):
        content = f"""Question: {entry.get("question", "")}
Intent: {entry.get("intent", "")}
Business Context: {entry.get("business_context", "")}
Tables Used: {", ".join(entry.get("tables_used", []))}
SQL Pattern: {entry.get("sql", "")}""".strip()
        metadata = {
            "type": "query",
            "intent": entry.get("intent", ""),
            "document_type": entry.get("document_type", ""),
            "tables_used": ",".join(entry.get("tables_used", [])),
            "sql": entry.get("sql", ""),
            "embedding_text": entry.get("embedding_text", ""),
        }
        documents.append(
            RagDocument(
                id=_stable_id("query", f"{index}:{entry.get('question', '')}"),
                content=content,
                embedding_text=entry.get("embedding_text", ""),
                metadata={**metadata, "content_hash": _content_hash(content, entry.get("embedding_text", ""), metadata)},
            )
        )
    return documents


class _EmbeddingModel:
    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(PURCHASE_RAG_EMBEDDING_MODEL, local_files_only=True)

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return [embedding.tolist() for embedding in embeddings]


class _PurchaseRagStore:
    def __init__(self):
        import chromadb

        self.embedding_model = _EmbeddingModel()
        self.client = chromadb.PersistentClient(path=str(PURCHASE_RAG_PERSIST_DIR))
        self.schema_collection = self.client.get_or_create_collection("purchase_tables")
        self.query_collection = self.client.get_or_create_collection("purchase_queries")
        self._ensure_indexed(self.schema_collection, _table_documents())
        self._ensure_indexed(self.query_collection, _query_documents())

    def _ensure_indexed(self, collection, documents: list[RagDocument]):
        existing_count = collection.count()
        if existing_count == len(documents):
            existing = collection.get(include=["metadatas"])
            existing_hashes = {
                doc_id: (metadata or {}).get("content_hash")
                for doc_id, metadata in zip(existing.get("ids") or [], existing.get("metadatas") or [])
            }
            desired_hashes = {document.id: document.metadata.get("content_hash") for document in documents}
            if existing_hashes == desired_hashes:
                return

        if existing_count:
            existing = collection.get(include=[])
            ids = existing.get("ids") or []
            if ids:
                collection.delete(ids=ids)

        embeddings = self.embedding_model.encode([doc.embedding_text or doc.content for doc in documents])
        collection.add(
            ids=[doc.id for doc in documents],
            documents=[doc.content for doc in documents],
            metadatas=[doc.metadata for doc in documents],
            embeddings=embeddings,
        )

    def _search(self, collection, question: str, top_k: int) -> list[dict[str, Any]]:
        embedding = self.embedding_model.encode([question])[0]
        raw = collection.query(query_embeddings=[embedding], n_results=top_k)
        results: list[dict[str, Any]] = []
        ids = raw.get("ids", [[]])[0]
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        for doc_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
            results.append(
                {
                    "id": doc_id,
                    "content": content,
                    "metadata": metadata,
                    "distance": distance,
                    "score": 1 / (1 + distance) if distance is not None else None,
                }
            )
        return results

    def retrieve(self, question: str, top_k_schema: int = 4, top_k_queries: int = 4) -> dict[str, list[dict[str, Any]]]:
        return {
            "schema": self._search(self.schema_collection, question, top_k_schema),
            "queries": self._search(self.query_collection, question, top_k_queries),
        }


class _LexicalPurchaseRagStore:
    def __init__(self):
        self.schema_documents = _table_documents()
        self.query_documents = _query_documents()

    def retrieve(self, question: str, top_k_schema: int = 4, top_k_queries: int = 4) -> dict[str, list[dict[str, Any]]]:
        return {
            "schema": _lexical_search(self.schema_documents, question, top_k_schema),
            "queries": _lexical_search(self.query_documents, question, top_k_queries),
        }


_STORE: _PurchaseRagStore | _LexicalPurchaseRagStore | None = None


def _get_store() -> _PurchaseRagStore | _LexicalPurchaseRagStore:
    global _STORE
    if _STORE is None:
        try:
            _STORE = _PurchaseRagStore()
        except Exception as exc:
            logger.warning("Purchase RAG vector store unavailable, using lexical retrieval: %s", exc)
            _STORE = _LexicalPurchaseRagStore()
    return _STORE


def _extract_sql(text: str) -> str:
    cleaned = text.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    match = re.search(r"\bselect\b.*", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if match:
        cleaned = match.group(0).strip()

    cleaned = cleaned.rstrip(";").strip()
    return cleaned


def _referenced_tables(sql: str) -> set[str]:
    return set(re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql.lower()))


def _validate_generated_sql(sql: str):
    if not sql.lower().startswith("select"):
        raise ValueError("RAG generated a non-SELECT query")
    if ";" in sql:
        raise ValueError("RAG generated multiple SQL statements")
    unknown_tables = _referenced_tables(sql) - ALLOWED_RAG_TABLES
    if unknown_tables:
        raise ValueError(f"RAG generated SQL with unsupported tables: {', '.join(sorted(unknown_tables))}")
    if _uses_balance_due_as_physical_column(sql):
        raise ValueError(
            'RAG generated SQL with unsupported physical column "BalanceDue"; '
            'derive AP invoice balance as ("DocTotal" - IFNULL("PaidToDate", 0))'
        )


def _uses_balance_due_as_physical_column(sql: str) -> bool:
    for match in re.finditer(r'(?:\b[a-z][a-z0-9_]*\.)?"BalanceDue"', sql, flags=re.IGNORECASE):
        preceding = sql[max(0, match.start() - 8) : match.start()].lower()
        if re.search(r"\bas\s+$", preceding):
            continue
        return True
    return False


def _build_sql_prompt(question: str, retrieval: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    schema_context = "\n\n--\n\n".join(item["content"] for item in retrieval["schema"])
    query_context = "\n\n--\n\n".join(item["content"] for item in retrieval["queries"])

    system = """You are an SAP HANA SQL generator for SAP Business One purchase-team fetch queries.

Return only one valid SAP HANA SELECT query.
Do not return markdown, explanations, comments, code fences, JSON, or multiple queries.

STRICT OUTPUT RULES:
- Output must contain exactly one SELECT statement.
- Never generate INSERT, UPDATE, DELETE, UPSERT, MERGE, DROP, ALTER, TRUNCATE, CREATE, REPLACE, EXECUTE, CALL, DO, GRANT, REVOKE, or transaction commands.
- Never use semicolons.
- Never use CTEs unless absolutely required.
- Never use dynamic SQL.
- Never generate procedural SQLScript blocks.
- Never use temporary tables.
- Never use wildcard SELECT * unless explicitly requested.
- Never hallucinate tables or columns.
- Never use tables outside this allowed list:
  opor, por1, opch, pch1, orpd, rpd1

SAP HANA SQL RULES:
- Use SAP HANA compatible SQL syntax only.
- Use lowercase unquoted table aliases.
- ALWAYS use double quotes for actual SAP Business One column names and match their exact case (e.g. "DocEntry", "DocNum", "CardCode", "CardName", "DocTotal", "DocDate", "DocStatus", "CANCELED", "ItemCode", "Quantity", "Price", "LineTotal", "TaxCode"). This is strictly required.
- Prefer ANSI JOIN syntax.
- Use LIMIT instead of TOP.
- Use CURRENT_DATE for current date.
- Use CURRENT_TIMESTAMP for current timestamp.
- Use IFNULL instead of ISNULL or NVL.
- Use || for string concatenation.
- Use CAST(value AS datatype) for conversions.
- Use TO_DATE only when necessary.
- Avoid database-specific syntax from MySQL, PostgreSQL, SQL Server, or Oracle.
- Do not use backticks.
- Do not use square brackets.
- Do not use PostgreSQL-only operators like ILIKE.
- Use LIKE for text matching.
- Use COALESCE or IFNULL for null handling.
- Cast final selected numeric measures to DOUBLE so HANA JSON responses contain numbers, not empty objects.
  This applies to amount, quantity, price, total, tax, discount, paid, pending, balance, and rate expressions.
  Example: CAST(p1."Quantity" AS DOUBLE) AS "Quantity", CAST(p1."Price" AS DOUBLE) AS "Price".
- Ensure all non-aggregated selected columns are included in GROUP BY.

SAP BUSINESS ONE CONTEXT:
- Purchase Orders:
  Header table: opor
  Row table: por1

- AP Invoices:
  Header table: opch
  Row table: pch1
  Balance due / pending amount is NOT a physical "BalanceDue" column.
  Derive it as ("DocTotal" - IFNULL("PaidToDate", 0)).
  You may alias that expression as "BalanceDue" or "pending_amount".

- Purchase Returns:
  Header table: orpd
  Row table: rpd1

STATUS RULES:
- "DocStatus" = 'O' means Open
- "DocStatus" = 'C' means Closed
- "CANCELED" = 'Y' means Cancelled
- "CANCELED" = 'N' means Active

BUSINESS RULES:
- Purchase orders represent procurement commitments.
- For top/ranked purchase order document lists, include useful line summary fields from por1 when possible:
  item summary, total quantity, average unit price, and document total.
- AP invoices represent actual vendor liabilities.
- For AP invoice pending amount, outstanding amount, unpaid amount, payable balance, or balance due,
  always use ("DocTotal" - IFNULL("PaidToDate", 0)); never select or filter on a physical "BalanceDue" column.
- AP invoice payment block is represented by opch."PayBlock" = 'Y' when that column is available.
- AP invoice lines based on purchase orders use pch1."BaseType" = 22, pch1."BaseEntry" = por1."DocEntry",
  and pch1."BaseLine" = por1."LineNum".
- PO-vs-invoice variance analysis should compare pch1 and por1 line values, quantities, prices, or tax codes.
- Purchase returns represent returns to vendors.
- Join header and row tables using:
  header."DocEntry" = row."DocEntry"

QUERY GENERATION RULES:
- Generate optimized SAP HANA analytical queries.
- Prefer explicit column selection.
- Prefer aggregation queries when user asks for totals, spending, quantities, or vendor analysis.
- Use ORDER BY for ranked outputs.
- Prefer LIMIT 10 for ranked/list queries unless user specifies another limit.
- Use meaningful aliases in lowercase.
- Use INNER JOIN unless LEFT JOIN is required.
- Avoid unnecessary nested subqueries.
- Ensure queries are read-only and safe.

DATE FILTER RULES:
- Use BETWEEN for ranges.
- Use ADD_DAYS, ADD_MONTHS, or ADD_YEARS when relative date logic is needed.
- Prefer filtering on document dates from header tables.

COMMON SAP B1 RELATIONS:
- opor joins por1 on "DocEntry"
- opch joins pch1 on "DocEntry"
- orpd joins rpd1 on "DocEntry"

PERFORMANCE RULES:
- Avoid SELECT DISTINCT unless necessary.
- Avoid Cartesian joins.
- Push filters early into WHERE clauses.
- Use aggregation efficiently.
- Avoid unnecessary ORDER BY on huge datasets unless ranking is requested.

OUTPUT FORMAT:
- Return only the SQL query text.
- No explanations.
- No markdown.
- No extra whitespace or formatting text."""

    context = f"""SCHEMA_DETAILS:
{schema_context if schema_context else "No schema details found"}

SIMILAR_SQL_EXAMPLES:
{query_context if query_context else "No similar examples found"}"""

    user = f"""USER_QUESTION:
{question}

SQL:"""
    return [
        {"role": "system", "content": system, "cache": True},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": user},
            ],
        },
    ]


def build_purchase_rag_fetch_sql(fetch_query: str) -> dict[str, Any]:
    question = fetch_query.strip()
    if not question:
        raise ValueError("Fetch query is empty")

    retrieval = _get_store().retrieve(question)
    raw_sql = claude_chat_completion(
        _build_sql_prompt(question, retrieval),
        temperature=0,
        max_tokens=1024,
        api_key=PURCHASE_TEAM_CLAUDE_API_KEY,
        model=PURCHASE_TEAM_CLAUDE_MODEL,
    )
    sql = make_numeric_select_json_safe(_extract_sql(raw_sql))
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
