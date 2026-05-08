import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.db.runtime import resolve_database_connection_string
from shared.env import load_agent_env


load_agent_env(__file__)

APP_NAME = "SAP B1 Purchase Supervisor Agent"
API_PREFIX = ""

SAP_BASE_URL = os.getenv("SAP_BASE_URL", "http://localhost:50000/b1s/v1")
SAP_USERNAME = os.getenv("SAP_USERNAME", "manager")
SAP_PASSWORD = os.getenv("SAP_PASSWORD", "password")
SAP_COMPANYDB = os.getenv("SAP_COMPANYDB", "SBODEMOUS")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "120"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b")

SQL_QUERY_TIMEOUT = int(os.getenv("SQL_QUERY_TIMEOUT", "30"))
DATABASE_CONNECTION_STRING = resolve_database_connection_string()

PURCHASE_ORDER_API_URL = os.getenv(
    "PURCHASE_ORDER_API_URL",
    "http://127.0.0.1:8000/purchase-orders/parse-and-execute",
)
AP_INVOICE_API_URL = os.getenv(
    "AP_INVOICE_API_URL",
    "http://127.0.0.1:8000/ap-invoices/parse-and-execute",
)
PURCHASE_RETURN_API_URL = os.getenv(
    "PURCHASE_RETURN_API_URL",
    "http://127.0.0.1:8000/purchase-returns/parse-and-execute",
)
