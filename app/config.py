import os
import sys
from pathlib import Path

from shared.db.runtime import resolve_database_connection_string
from shared.env import load_agent_env

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_agent_env(__file__)

APP_NAME = "SAP B1 ERP Big Supervisor Agent"

SAP_BASE_URL = os.getenv("SAP_BASE_URL", "http://localhost:50000/b1s/v1")
SAP_USERNAME = os.getenv("SAP_USERNAME", "manager")
SAP_PASSWORD = os.getenv("SAP_PASSWORD", "password")
SAP_COMPANYDB = os.getenv("SAP_COMPANYDB", "SBODEMOUS")

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
CLAUDE_BASE_URL = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7"))
CLAUDE_API_VERSION = os.getenv("CLAUDE_API_VERSION", "2023-06-01")
CLAUDE_PROMPT_CACHE = os.getenv("CLAUDE_PROMPT_CACHE", "true").strip().lower() in {"1", "true", "yes", "on"}
BIG_SUPERVISOR_CLAUDE_API_KEY = os.getenv("BIG_SUPERVISOR_CLAUDE_API_KEY", CLAUDE_API_KEY)
BIG_SUPERVISOR_CLAUDE_MODEL = os.getenv("BIG_SUPERVISOR_CLAUDE_MODEL", CLAUDE_MODEL)
PURCHASE_TEAM_CLAUDE_API_KEY = os.getenv("PURCHASE_TEAM_CLAUDE_API_KEY", CLAUDE_API_KEY)
PURCHASE_TEAM_CLAUDE_MODEL = os.getenv("PURCHASE_TEAM_CLAUDE_MODEL", CLAUDE_MODEL)
SALES_TEAM_CLAUDE_API_KEY = os.getenv("SALES_TEAM_CLAUDE_API_KEY", CLAUDE_API_KEY)
SALES_TEAM_CLAUDE_MODEL = os.getenv("SALES_TEAM_CLAUDE_MODEL", CLAUDE_MODEL)
SALES_SQL_CLAUDE_API_KEY = os.getenv("SALES_SQL_CLAUDE_API_KEY", SALES_TEAM_CLAUDE_API_KEY)
SALES_SQL_CLAUDE_MODEL = os.getenv("SALES_SQL_CLAUDE_MODEL", SALES_TEAM_CLAUDE_MODEL)
CHAT_RESPONSE_CLAUDE_API_KEY = os.getenv("CHAT_RESPONSE_CLAUDE_API_KEY", CLAUDE_API_KEY)
CHAT_RESPONSE_CLAUDE_MODEL = os.getenv("CHAT_RESPONSE_CLAUDE_MODEL", CLAUDE_MODEL)

# Groq setup is intentionally dormant for now. Keep Claude as the active provider.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "60"))

DATABASE_CONNECTION_STRING = resolve_database_connection_string()

SQL_QUERY_TIMEOUT = int(os.getenv("SQL_QUERY_TIMEOUT", "30"))
HANA_SQL_API_URL = os.getenv(
    "HANA_SQL_API_URL",
    "http://vzone.in:1662/api/GetMethod/GetData",
)
HANA_SQL_API_TOKEN = os.getenv("HANA_SQL_API_TOKEN", "")
HANA_SQL_API_KEY = os.getenv("HANA_SQL_API_KEY", "")
HANA_SQL_API_AUTH_SCHEME = os.getenv("HANA_SQL_API_AUTH_SCHEME", "Bearer")
HANA_SQL_API_HEADERS = os.getenv("HANA_SQL_API_HEADERS", "")


def _resolve_path_env(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else REPO_ROOT / value


PURCHASE_RAG_EMBEDDING_MODEL = os.getenv("PURCHASE_RAG_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
PURCHASE_RAG_PERSIST_DIR = _resolve_path_env("PURCHASE_RAG_PERSIST_DIR", ".rag_chroma/purchase")

SALES_RAG_EMBEDDING_MODEL = os.getenv("SALES_RAG_EMBEDDING_MODEL", PURCHASE_RAG_EMBEDDING_MODEL)
SALES_RAG_PERSIST_DIR = _resolve_path_env("SALES_RAG_PERSIST_DIR", ".rag_chroma/sales")
SALES_RAG_USE_VECTOR = os.getenv("SALES_RAG_USE_VECTOR", "false").strip().lower() in {"1", "true", "yes", "on"}
