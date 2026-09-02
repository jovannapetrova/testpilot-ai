from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from models.database import Base

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "storage" / "testpilot.db"
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if DATABASE_URL == "sqlite:///:memory:":
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, pool_pre_ping=True, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    apply_lightweight_migrations()


def apply_lightweight_migrations() -> None:
    """Apply additive migrations for existing SQLite/PostgreSQL installs.

    This keeps local onboarding simple while avoiding the production foot-gun
    where create_all() creates missing tables but never adds new columns.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "users" in tables:
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "password_changed_at" not in columns:
            _execute_ddl("ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP")

    if "projects" in tables:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        if "current_stage" not in columns:
            _execute_ddl("ALTER TABLE projects ADD COLUMN current_stage VARCHAR(160)")
        if "started_at" not in columns:
            _execute_ddl("ALTER TABLE projects ADD COLUMN started_at TIMESTAMP")

    for statement in [
        "CREATE INDEX IF NOT EXISTS ix_users_created_at ON users (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_projects_created_at ON projects (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_projects_updated_at ON projects (updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_reports_created_at ON reports (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens (user_id)",
    ]:
        _execute_ddl(statement)


def _execute_ddl(statement: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(statement))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
