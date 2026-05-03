import sqlite3
from datetime import datetime, date, timedelta

from flask import Flask, render_template, redirect, url_for, request, flash, abort, session
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import (
    get_user_by_id, get_summary_stats,
    get_recent_transactions, get_category_breakdown,
)
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


def _subtract_months(d, n):
    month = d.month - n
    year  = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, 1)


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])
    if user is None:
        abort(404)

    from_str = request.args.get("from", "").strip()
    to_str   = request.args.get("to",   "").strip()

    date_from = date_to_parsed = None
    active_period = "all_time"

    if from_str and to_str:
        try:
            date_from      = datetime.strptime(from_str, "%Y-%m-%d").date()
            date_to_parsed = datetime.strptime(to_str,   "%Y-%m-%d").date()
        except ValueError:
            abort(400)

        today               = date.today()
        this_month_start    = today.replace(day=1)
        last_month_end      = this_month_start - timedelta(days=1)
        last_month_start    = last_month_end.replace(day=1)
        last_3_months_start = _subtract_months(today, 2)

        if date_from == this_month_start and date_to_parsed == today:
            active_period = "this_month"
        elif date_from == last_month_start and date_to_parsed == last_month_end:
            active_period = "last_month"
        elif date_from == last_3_months_start and date_to_parsed == today:
            active_period = "last_3_months"
        else:
            active_period = "custom"

    df_str = date_from.strftime("%Y-%m-%d")      if date_from      else None
    dt_str = date_to_parsed.strftime("%Y-%m-%d") if date_to_parsed else None

    today               = date.today()
    this_month_start    = today.replace(day=1)
    last_month_end      = this_month_start - timedelta(days=1)
    last_month_start    = last_month_end.replace(day=1)
    last_3_months_start = _subtract_months(today, 2)

    preset_urls = {
        "this_month":    url_for("profile", **{"from": this_month_start.strftime("%Y-%m-%d"),
                                               "to":   today.strftime("%Y-%m-%d")}),
        "last_month":    url_for("profile", **{"from": last_month_start.strftime("%Y-%m-%d"),
                                               "to":   last_month_end.strftime("%Y-%m-%d")}),
        "last_3_months": url_for("profile", **{"from": last_3_months_start.strftime("%Y-%m-%d"),
                                               "to":   today.strftime("%Y-%m-%d")}),
        "all_time":      url_for("profile"),
    }

    stats        = get_summary_stats(session["user_id"],       date_from=df_str, date_to=dt_str)
    transactions = get_recent_transactions(session["user_id"], date_from=df_str, date_to=dt_str)
    categories   = get_category_breakdown(session["user_id"],  date_from=df_str, date_to=dt_str)

    return render_template(
        "profile.html",
        user=user, stats=stats, transactions=transactions, categories=categories,
        date_from=from_str, date_to=to_str,
        active_period=active_period, preset_urls=preset_urls,
    )


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
