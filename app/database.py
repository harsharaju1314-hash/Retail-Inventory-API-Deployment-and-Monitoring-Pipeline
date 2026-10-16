import os
import sqlite3
from typing import Optional, Tuple
from flask import Flask, current_app, g

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sku TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    price REAL NOT NULL CHECK(price > 0),
    stock_quantity INTEGER NOT NULL CHECK(stock_quantity >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
"""


def get_db_path(app: Optional[Flask] = None) -> str:
    """Retrieve database path from app config, env var, or fallback default."""
    if app and "DATABASE_PATH" in app.config:
        return app.config["DATABASE_PATH"]
    if current_app and "DATABASE_PATH" in current_app.config:
        return current_app.config["DATABASE_PATH"]
    return os.getenv("DATABASE_PATH", "data/inventory.db")


def get_db():
    """
    Get or create a per-request SQLite connection.
    Connections are stored in Flask application context (g) and closed on teardown.
    """
    if "db" not in g:
        db_path = get_db_path()

        # Ensure parent directory exists for file-based DBs
        if db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            timeout=10.0,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")

        g.db = conn

    return g.db


def close_db(e=None):
    """Close the database connection on request teardown."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app: Optional[Flask] = None):
    """Initialize database tables and indexes."""
    db_path = get_db_path(app)
    if db_path != ":memory:":
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def check_db_connection() -> Tuple[bool, Optional[str]]:
    """
    Execute a lightweight query to verify SQLite health.
    Returns (True, None) if healthy, or (False, error_str) on failure.
    """
    try:
        db = get_db()
        db.execute("SELECT 1").fetchone()
        return True, None
    except Exception as exc:
        return False, str(exc)
