from database.db import get_db


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    try:
        sql = (
            "SELECT date, description, category, amount "
            "FROM expenses WHERE user_id = ?"
        )
        params = (user_id,)
        if date_from is not None and date_to is not None:
            sql += " AND date BETWEEN ? AND ?"
            params += (date_from, date_to)
        sql += " ORDER BY date DESC LIMIT ?"
        params += (limit,)
        rows = conn.execute(sql, params).fetchall()
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


def get_summary_stats(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        base_where = "WHERE user_id = ?"
        base_params = (user_id,)
        if date_from is not None and date_to is not None:
            base_where += " AND date BETWEEN ? AND ?"
            base_params += (date_from, date_to)
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses " + base_where,
            base_params,
        ).fetchone()
        top_row = conn.execute(
            "SELECT category FROM expenses " + base_where +
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            base_params,
        ).fetchone()
        return {
            "total_spent": f"₹{row['total']:,.2f}",
            "transaction_count": row["cnt"],
            "top_category": top_row["category"] if top_row else "—",
        }
    finally:
        conn.close()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        sql = (
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ?"
        )
        params = (user_id,)
        if date_from is not None and date_to is not None:
            sql += " AND date BETWEEN ? AND ?"
            params += (date_from, date_to)
        sql += " GROUP BY category ORDER BY total DESC"
        rows = conn.execute(sql, params).fetchall()
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
