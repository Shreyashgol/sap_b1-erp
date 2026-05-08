import logging
import os
from contextlib import contextmanager


DEFAULT_DATABASE_URL_TEMPLATE = "postgresql://postgres:password@localhost:5432/{database_name}"


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def resolve_database_connection_string(default_database_name: str = "sap_agents_db") -> str:
    raw_value = (
        os.getenv("SAP_AGENTS_DATABASE_URL")
        or os.getenv("DATABASE_CONNECTION_STRING")
        or os.getenv("DATABASE_URL")
        or DEFAULT_DATABASE_URL_TEMPLATE.format(database_name=default_database_name)
    )
    return normalize_database_url(raw_value)


class DatabaseRuntime:
    def __init__(self, database_url: str, metadata, logger_name: str | None = None):
        self.database_url = database_url
        self.metadata = metadata
        self.logger = logging.getLogger(logger_name or __name__)
        self.engine = None
        self.session_local = None

    def init(self):
        if self.engine is not None and self.session_local is not None:
            return self.engine

        if not self.database_url:
            self.logger.warning("DATABASE_CONNECTION_STRING is empty; database persistence is disabled")
            return None

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        try:
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                future=True,
            )
            self.session_local = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
            self.metadata.create_all(bind=self.engine)
            self.logger.info("Shared SQLAlchemy engine initialized")
            return self.engine
        except Exception as exc:
            if "postgres:password@" in self.database_url:
                raise RuntimeError(
                    "PostgreSQL connection failed while using placeholder default credentials. "
                    "Set SAP_AGENTS_DATABASE_URL to your real database URL, for example "
                    "'postgresql://<user>:<password>@localhost:5432/sap_agents_db'."
                ) from exc
            raise

    @contextmanager
    def session_scope(self):
        self.init()
        if self.session_local is None:
            raise RuntimeError("DATABASE_CONNECTION_STRING is not configured")

        session = self.session_local()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
