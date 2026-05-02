import sqlite3
import pytest
from unittest.mock import patch


# ── helpers ────────────────────────────────────────────────────────────────

def make_in_memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
    """)
    return conn


@pytest.fixture()
def db_with_user_and_expenses():
    conn = make_in_memory_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Test User", "test@example.com", "hashed", "2026-01-15 10:00:00"),
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, 100.00, "Food",      "2026-05-01", "Lunch"),
            (user_id, 200.00, "Transport", "2026-05-10", "Taxi"),
            (user_id, 300.00, "Bills",     "2026-05-20", "Electric"),
        ],
    )
    conn.commit()
    yield conn, user_id
    conn.close()


@pytest.fixture()
def db_with_user_no_expenses():
    conn = make_in_memory_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Empty User", "empty@example.com", "hashed", "2026-03-01 09:00:00"),
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    yield conn, user_id
    conn.close()


# ── get_recent_transactions tests ──────────────────────────────────────────

def test_get_recent_transactions_with_expenses(db_with_user_and_expenses):
    conn, user_id = db_with_user_and_expenses
    from database.queries import get_recent_transactions
    with patch("database.queries.get_db", return_value=conn):
        result = get_recent_transactions(user_id)
    assert len(result) == 3
    assert result[0]["date"] == "2026-05-20"   # newest first
    assert result[2]["date"] == "2026-05-01"   # oldest last
    assert result[0]["amount"] == "₹300.00"
    assert "category" in result[0]
    assert "description" in result[0]


def test_get_recent_transactions_no_expenses(db_with_user_no_expenses):
    conn, user_id = db_with_user_no_expenses
    from database.queries import get_recent_transactions
    with patch("database.queries.get_db", return_value=conn):
        result = get_recent_transactions(user_id)
    assert result == []


def test_get_recent_transactions_limit(db_with_user_and_expenses):
    conn, user_id = db_with_user_and_expenses
    from database.queries import get_recent_transactions
    with patch("database.queries.get_db", return_value=conn):
        result = get_recent_transactions(user_id, limit=2)
    assert len(result) == 2


# ── get_user_by_id tests ───────────────────────────────────────────────────

def test_get_user_by_id_valid(db_with_user_and_expenses):
    conn, user_id = db_with_user_and_expenses
    from database.queries import get_user_by_id
    with patch("database.queries.get_db", return_value=conn):
        result = get_user_by_id(user_id)
    assert result is not None
    assert result["name"] == "Test User"
    assert result["email"] == "test@example.com"
    assert result["initials"] == "TU"
    assert result["member_since"] == "January 2026"


def test_get_user_by_id_missing(db_with_user_and_expenses):
    conn, _ = db_with_user_and_expenses
    from database.queries import get_user_by_id
    with patch("database.queries.get_db", return_value=conn):
        result = get_user_by_id(99999)
    assert result is None


# ── get_summary_stats tests ────────────────────────────────────────────────

def test_get_summary_stats_with_expenses(db_with_user_and_expenses):
    conn, user_id = db_with_user_and_expenses
    from database.queries import get_summary_stats
    with patch("database.queries.get_db", return_value=conn):
        result = get_summary_stats(user_id)
    assert result["transaction_count"] == 3
    assert result["total_spent"] == "₹600.00"
    assert result["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(db_with_user_no_expenses):
    conn, user_id = db_with_user_no_expenses
    from database.queries import get_summary_stats
    with patch("database.queries.get_db", return_value=conn):
        result = get_summary_stats(user_id)
    assert result["transaction_count"] == 0
    assert result["total_spent"] == "₹0.00"
    assert result["top_category"] == "—"


# ── get_category_breakdown tests ───────────────────────────────────────────

def test_get_category_breakdown_with_expenses(db_with_user_and_expenses):
    conn, user_id = db_with_user_and_expenses
    from database.queries import get_category_breakdown
    with patch("database.queries.get_db", return_value=conn):
        result = get_category_breakdown(user_id)
    assert len(result) == 3
    # Ordered by total descending
    assert result[0]["name"] == "Bills"
    assert result[0]["total"] == "₹300.00"
    # pcts are integers summing to 100
    assert all(isinstance(r["pct"], int) for r in result)
    assert sum(r["pct"] for r in result) == 100


def test_get_category_breakdown_no_expenses(db_with_user_no_expenses):
    conn, user_id = db_with_user_no_expenses
    from database.queries import get_category_breakdown
    with patch("database.queries.get_db", return_value=conn):
        result = get_category_breakdown(user_id)
    assert result == []
