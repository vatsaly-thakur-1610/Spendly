from database.db import get_db


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount "
            "FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [
            {
                "date": row["date"],
                "description": row["description"],
                "category": row["category"],
                "amount": f"₹{row['amount']:,.2f}",
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_user_by_id(user_id):
    from datetime import datetime
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        words = row["name"].split()
        initials = "".join(w[0].upper() for w in words[:2])
        dt = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
        member_since = dt.strftime("%B %Y")
        return {
            "name": row["name"],
            "email": row["email"],
            "initials": initials,
            "member_since": member_since,
        }
    finally:
        conn.close()


def get_summary_stats(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top_row = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return {
            "total_spent": f"₹{row['total']:,.2f}",
            "transaction_count": row["cnt"],
            "top_category": top_row["category"] if top_row else "—",
        }
    finally:
        conn.close()


def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
        if not rows:
            return []
        grand_total = sum(row["total"] for row in rows)
        pcts = [round(row["total"] * 100 / grand_total) for row in rows]
        diff = 100 - sum(pcts)
        pcts[0] += diff  # absorb rounding remainder into largest category
        return [
            {
                "name": row["category"],
                "total": f"₹{row['total']:,.2f}",
                "pct": pct,
            }
            for row, pct in zip(rows, pcts)
        ]
    finally:
        conn.close()
