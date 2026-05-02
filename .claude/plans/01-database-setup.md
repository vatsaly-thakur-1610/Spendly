# Plan: Database Setup (Step 1)

## Context

Spendly needs a working data layer before any auth or expense features can be built. `database/db.py` currently contains only stub comments. This plan implements the three required helpers (`get_db`, `init_db`, `seed_db`) and wires them into `app.py` on startup.

---

## Files Changed

- `database/db.py` — full implementation
- `app.py` — added imports and startup initialization

---

## Schema

### users
| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK, autoincrement |
| name | TEXT | NOT NULL |
| email | TEXT | UNIQUE, NOT NULL |
| password_hash | TEXT | NOT NULL |
| created_at | TEXT | DEFAULT datetime('now') |

### expenses
| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | PK, autoincrement |
| user_id | INTEGER | FK → users.id, NOT NULL |
| amount | REAL | NOT NULL |
| category | TEXT | NOT NULL |
| date | TEXT | NOT NULL (YYYY-MM-DD) |
| description | TEXT | nullable |
| created_at | TEXT | DEFAULT datetime('now') |

---

## Key Decisions

- `DB_PATH` resolved relative to `db.py` so it always points to project root
- `init_db` uses `executescript` for clean multi-table DDL in one call
- `seed_db` guards with `COUNT(*) > 0` on users — fully idempotent
- `app.app_context()` block at module level so DB is ready under both direct run and WSGI

---

## Verification

```bash
python app.py                          # starts on port 5001, no errors
python -c "from database.db import get_db; print(list(get_db().execute('SELECT name, email FROM users')))"
python -c "from database.db import get_db; print(get_db().execute('SELECT COUNT(*) FROM expenses').fetchone()[0])"
pytest
```
