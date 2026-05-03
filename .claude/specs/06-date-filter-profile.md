# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the profile page so users can narrow all
four data sections — summary stats, transaction history, and category breakdown
— to a specific time window. The filter is submitted as GET query parameters
(`from` and `to`) so the filtered view is bookmarkable and shareable. Predefined
period shortcuts (This Month, Last Month, Last 3 Months, All Time) let users
jump to common windows without typing dates, while a custom date picker covers
arbitrary ranges. All query helpers are updated to accept optional date bounds;
when no bounds are supplied the behaviour is identical to the current "all time"
view, keeping the route backwards-compatible.

## Depends on
- Step 1: Database setup (`expenses` table with `date` column exists)
- Step 2: Registration (users exist in the database)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page design (template structure already in place)
- Step 5: Backend connection (all four query helpers exist in `database/queries.py`)

## Routes
No new routes. The existing `GET /profile` route is extended to read optional
`from` and `to` query parameters (ISO date strings, e.g. `?from=2026-01-01&to=2026-01-31`).

## Database changes
No database changes. The `expenses.date` column (`TEXT` in ISO format) already
supports date-range comparisons with SQL `BETWEEN`.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar above the stats row containing:
    - Four preset shortcut buttons: **This Month**, **Last Month**, **Last 3 Months**, **All Time**
    - A **Custom** section with two `<input type="date">` fields (From / To) and an **Apply** button
  - The active preset button must receive an `active` CSS class so it is visually distinguished
  - The existing stats, transaction table, and category breakdown sections are unchanged structurally; they already consume the variables passed from the route

## Files to change
- `app.py`
  - In the `profile()` view: read `request.args.get("from")` and `request.args.get("to")`
  - Validate that both values, if supplied, are valid ISO dates (`YYYY-MM-DD`); use `abort(400)` for malformed input
  - Pass `date_from` and `date_to` to all four query helpers
  - Pass `date_from`, `date_to`, and a computed `active_period` string to the template for rendering the active shortcut button
- `database/queries.py`
  - Add optional `date_from=None` and `date_to=None` keyword arguments to `get_summary_stats`, `get_recent_transactions`, and `get_category_breakdown`
  - When both are supplied, append `AND date BETWEEN ? AND ?` to each query's WHERE clause
  - `get_user_by_id` does not filter by date and requires no changes
- `static/css/profile.css`
  - Add styles for `.filter-bar`, `.filter-presets`, `.filter-preset-btn`, `.filter-preset-btn.active`, `.filter-custom`, and the custom date inputs

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never f-strings or string concatenation in SQL
- Date validation in the route must use `datetime.strptime(value, "%Y-%m-%d")` wrapped in a `try/except ValueError`; call `abort(400)` on failure
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles (the `style="width: {{ cat.pct }}%"` on the bar fill that already exists is the sole exception — do not add new ones)
- Filter form must use `method="GET"` so the URL reflects the active filter
- Preset shortcuts must be `<a>` tags that construct the correct `?from=&to=` URL — not JavaScript-only buttons — so they work without JS
- `active_period` must be one of `"this_month"`, `"last_month"`, `"last_3_months"`, `"all_time"`, or `"custom"`; the route computes this by comparing `date_from`/`date_to` against today's date
- When `date_from` and `date_to` are absent (All Time), all existing behaviour is preserved exactly

## Definition of done
- [ ] Visiting `/profile` with no query params shows all transactions (identical to Step 5 behaviour)
- [ ] Clicking **This Month** reloads `/profile?from=YYYY-MM-01&to=YYYY-MM-DD` (current month bounds) and shows only that month's transactions and stats
- [ ] Clicking **Last Month** reloads with the previous month's bounds and stats update accordingly
- [ ] Clicking **Last 3 Months** shows transactions and stats from the last 90 days
- [ ] Clicking **All Time** reloads `/profile` with no query params and shows everything
- [ ] Entering a custom date range and clicking **Apply** filters correctly
- [ ] The active preset button has a visually distinct style compared to inactive ones
- [ ] If only one of `from` or `to` is supplied, the filter treats it as All Time (no partial filter)
- [ ] Supplying a malformed date (e.g. `?from=not-a-date`) returns HTTP 400
- [ ] Summary stats (total spent, transaction count, top category) update to reflect only the filtered period
- [ ] Category breakdown updates to reflect only the filtered period
- [ ] An authenticated user with no expenses in the selected range sees ₹0.00 total, 0 transactions, and an empty breakdown — no errors
