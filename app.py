import sqlite3

from flask import Flask, render_template, redirect, url_for, request, flash, abort, session
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            return render_template("register.html", error="All fields are required.")
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match.")
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Email already registered.")

        flash("Account created! Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    user = get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "error")
        return render_template("login.html")
    session["user_id"] = user["id"]
    session["user_email"] = user["email"]
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Nitish Kumar",
        "email": "nitish@spendly.com",
        "initials": "NK",
        "member_since": "January 2025",
    }
    stats = {
        "total_spent": "₹6,105.00",
        "transaction_count": 8,
        "top_category": "Shopping",
    }
    transactions = [
        {"date": "2026-05-01", "description": "Grocery run",       "category": "Food",          "amount": "₹450.00"},
        {"date": "2026-05-03", "description": "Metro card top-up", "category": "Transport",     "amount": "₹120.00"},
        {"date": "2026-05-05", "description": "Electricity bill",  "category": "Bills",         "amount": "₹1,800.00"},
        {"date": "2026-05-08", "description": "Pharmacy",          "category": "Health",        "amount": "₹300.00"},
        {"date": "2026-05-10", "description": "Movie + dinner",    "category": "Entertainment", "amount": "₹650.00"},
        {"date": "2026-05-15", "description": "New shoes",         "category": "Shopping",      "amount": "₹2,200.00"},
        {"date": "2026-05-18", "description": "Coffee and snacks", "category": "Food",          "amount": "₹85.00"},
        {"date": "2026-05-22", "description": "Miscellaneous",     "category": "Other",         "amount": "₹500.00"},
    ]
    categories = [
        {"name": "Shopping",      "total": "₹2,200.00", "pct": 36},
        {"name": "Bills",         "total": "₹1,800.00", "pct": 30},
        {"name": "Entertainment", "total": "₹650.00",   "pct": 11},
        {"name": "Food",          "total": "₹535.00",   "pct": 9},
        {"name": "Other",         "total": "₹500.00",   "pct": 8},
        {"name": "Health",        "total": "₹300.00",   "pct": 5},
        {"name": "Transport",     "total": "₹120.00",   "pct": 2},
    ]
    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
