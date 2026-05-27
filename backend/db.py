"""SQLAlchemy engine + session setup for MoneyMind.

Database selection (in priority order):
  1. DATABASE_URL env var  → use it (Postgres on Render/Supabase/Neon)
  2. Otherwise              → SQLite at <project_root>/data/moneymind.db

Heroku/Render-style postgres:// URLs are auto-rewritten to postgresql://
so SQLAlchemy 2.0 accepts them.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "moneymind.db")

# ─── Pick the database backend ─────────────────────────────────────────────
_env_url = os.environ.get("DATABASE_URL", "").strip()

if _env_url:
    # Render/Heroku give postgres:// but SQLAlchemy 2.0 wants postgresql://
    if _env_url.startswith("postgres://"):
        _env_url = _env_url.replace("postgres://", "postgresql://", 1)
    DB_URL = _env_url
    _is_sqlite = False
else:
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_URL = f"sqlite:///{DB_PATH}"
    _is_sqlite = True

# `check_same_thread=False` only applies to SQLite. For Postgres we pass {}.
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    DB_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,   # auto-reconnect dropped Postgres connections
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they don't exist."""
    # Import here so models register on Base.metadata before create_all.
    from backend import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_session():
    """Yield a session; caller responsible for closing (or use a context manager)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
