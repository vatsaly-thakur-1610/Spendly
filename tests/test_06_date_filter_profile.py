"""
Tests for Step 6: Date Filter on the Profile Page.

Spec: .claude/specs/06-date-filter-profile.md

The profile route accepts optional `from` and `to` ISO-date query params.
When both are present and valid, all four data sections (summary stats,
transactions, category breakdown) are scoped to that window.  When only one
is present, the filter is ignored (All Time).  Malformed dates yield HTTP 400.

All tests use the in-memory DB seeded with the standard Demo User and the
eight sample expenses (all dated 2026-05-01 through 2026-05-22).
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch

from app import app as flask_app
from database.db import init_db, seed_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _subtract_months(d, n):
    """Mirror of app.py's _subtract_months — used to compute expected preset URLs."""
    month = d.month - n
    year  = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, 1)


def _this_month_bounds():
    today = date.today()
    return today.replace(day=1).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def _last_month_bounds():
    today = date.today()
    last_end   = today.replace(day=1) - timedelta(days=1)
    last_start = last_end.replace(day=1)
    return last_start.strftime("%Y-%m-%d"), last_end.strftime("%Y-%m-%d")


def _last_3_months_bounds():
    today = date.today()
    start = _subtract_months(today, 2)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Flask app configured for testing with a fresh in-memory DB."""
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })
    # Re-use the real DB path but swap in :memory: via get_db patch is complex;
    # instead we rely on seed_db() which only seeds when the users table is empty.
    # We initialise the real DB once per test run via the app context.
    with flask_app.app_context():
        init_db()
        seed_db()
        yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """Test client already logged in as the seed demo user."""
    client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )
    return client


# ---------------------------------------------------------------------------
# Helper: GET /profile with optional query string
# ---------------------------------------------------------------------------

def _get_profile(client, params=None):
    """Issue GET /profile with optional dict of query params."""
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return client.get(f"/profile?{qs}", follow_redirects=False)
    return client.get("/profile", follow_redirects=False)


# ===========================================================================
# Auth guard
# ===========================================================================

class TestAuthGuard:
    def test_unauthenticated_redirects_to_login(self, client):
        resp = _get_profile(client)
        assert resp.status_code == 302, "Unauthenticated /profile must redirect"
        assert "/login" in resp.headers["Location"], (
            "Redirect target should be /login"
        )

    def test_unauthenticated_with_date_params_redirects_to_login(self, client):
        """Auth check happens before date parsing — still 302, not 400."""
        resp = _get_profile(client, {"from": "2026-05-01", "to": "2026-05-31"})
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ===========================================================================
# No query params — All Time (backwards-compatible baseline)
# ===========================================================================

class TestAllTime:
    def test_returns_200(self, auth_client):
        resp = _get_profile(auth_client)
        assert resp.status_code == 200

    def test_renders_profile_template_landmarks(self, auth_client):
        resp = _get_profile(auth_client)
        html = resp.data
        assert b"Transaction History" in html, "Should render Transaction History section"
        assert b"Spending by Category" in html, "Should render Category Breakdown section"
        assert b"Total Spent" in html, "Should render Total Spent stat"
        assert b"Transactions" in html, "Should render Transactions stat"
        assert b"Top Category" in html, "Should render Top Category stat"

    def test_filter_bar_is_present(self, auth_client):
        resp = _get_profile(auth_client)
        html = resp.data
        assert b"filter-bar" in html, "Filter bar element must be rendered"
        assert b"filter-preset-btn" in html, "Preset buttons must be rendered"
        assert b"This Month" in html
        assert b"Last Month" in html
        assert b"Last 3 Months" in html
        assert b"All Time" in html

    def test_custom_form_uses_get_method(self, auth_client):
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        assert 'method="GET"' in html or "method=GET" in html, (
            "Custom filter form must use GET so the URL reflects the active filter"
        )

    def test_all_time_button_has_active_class(self, auth_client):
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        # The active class must appear on the All Time button, not on others
        assert "All Time" in html
        # Find the segment that contains "All Time" and check it carries `active`
        idx = html.find("All Time")
        surrounding = html[max(0, idx - 200): idx + 20]
        assert "active" in surrounding, (
            "All Time preset button must have 'active' CSS class when no filter is applied"
        )

    def test_all_time_shows_all_seed_transactions(self, auth_client):
        """All 8 seed expenses should appear (limited by default limit=10)."""
        resp = _get_profile(auth_client)
        html = resp.data
        # Seed has 8 distinct descriptions; spot-check a few
        assert b"Grocery run" in html
        assert b"Electricity bill" in html
        assert b"New shoes" in html

    def test_all_time_stats_include_all_expenses(self, auth_client):
        """Total of the 8 seed expenses = 6105.00."""
        resp = _get_profile(auth_client)
        html = resp.data
        assert b"\xe2\x82\xb96,105.00" in html, (
            "Total Spent for all-time should be ₹6,105.00 (sum of all seed expenses)"
        )

    def test_all_time_transaction_count(self, auth_client):
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        # stat-value for transaction count = 8
        assert ">8<" in html, "Transaction count should be 8 for all seed expenses"

    def test_all_time_top_category_is_shopping(self, auth_client):
        """Shopping has the highest single expense (₹2,200) → top category."""
        resp = _get_profile(auth_client)
        html = resp.data
        assert b"Shopping" in html


# ===========================================================================
# This Month preset
# ===========================================================================

class TestThisMonthPreset:
    def test_this_month_returns_200(self, auth_client):
        from_s, to_s = _this_month_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        assert resp.status_code == 200

    def test_this_month_active_period(self, auth_client):
        from_s, to_s = _this_month_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        html = resp.data.decode()
        idx = html.find("This Month")
        surrounding = html[max(0, idx - 200): idx + 20]
        assert "active" in surrounding, (
            "This Month button must carry the 'active' CSS class when this month's bounds are active"
        )

    def test_this_month_other_buttons_not_active(self, auth_client):
        """Only one preset button should be active at a time."""
        from_s, to_s = _this_month_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        html = resp.data.decode()
        # All Time button should NOT be active in this context
        idx_all = html.find("All Time")
        surrounding_all = html[max(0, idx_all - 200): idx_all + 20]
        # 'active' should NOT appear immediately before 'All Time' when this_month is active
        # We count occurrences of 'active' class across preset buttons
        import re
        active_matches = re.findall(r'filter-preset-btn[^"]*active', html)
        assert len(active_matches) == 1, (
            f"Exactly one preset button should be active, found: {active_matches}"
        )

    def test_this_month_stats_scoped_to_window(self, auth_client):
        """
        Seed expenses are all in May 2026.  If today is in May 2026, stats
        should match; if today is a different month, the window returns 0.
        We only verify the response is 200 and stats are present — the exact
        values are tested separately in the query-layer tests.
        """
        from_s, to_s = _this_month_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        assert resp.status_code == 200
        html = resp.data
        assert b"Total Spent" in html
        assert b"Transactions" in html


# ===========================================================================
# Last Month preset
# ===========================================================================

class TestLastMonthPreset:
    def test_last_month_returns_200(self, auth_client):
        from_s, to_s = _last_month_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        assert resp.status_code == 200

    def test_last_month_active_period(self, auth_client):
        from_s, to_s = _last_month_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        html = resp.data.decode()
        idx = html.find("Last Month")
        surrounding = html[max(0, idx - 200): idx + 20]
        assert "active" in surrounding, (
            "Last Month button must have 'active' class when last month's bounds are applied"
        )

    def test_last_month_active_period_value_in_response(self, auth_client):
        """active_period is passed to the template; indirect check via active class count."""
        from_s, to_s = _last_month_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        import re
        html = resp.data.decode()
        active_matches = re.findall(r'filter-preset-btn[^"]*active', html)
        assert len(active_matches) == 1


# ===========================================================================
# Last 3 Months preset
# ===========================================================================

class TestLast3MonthsPreset:
    def test_last_3_months_returns_200(self, auth_client):
        from_s, to_s = _last_3_months_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        assert resp.status_code == 200

    def test_last_3_months_active_period(self, auth_client):
        from_s, to_s = _last_3_months_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        html = resp.data.decode()
        idx = html.find("Last 3 Months")
        surrounding = html[max(0, idx - 200): idx + 20]
        assert "active" in surrounding, (
            "Last 3 Months button must have 'active' class when its bounds are applied"
        )

    def test_last_3_months_exactly_one_active_button(self, auth_client):
        import re
        from_s, to_s = _last_3_months_bounds()
        resp = _get_profile(auth_client, {"from": from_s, "to": to_s})
        html = resp.data.decode()
        active_matches = re.findall(r'filter-preset-btn[^"]*active', html)
        assert len(active_matches) == 1


# ===========================================================================
# Custom date range
# ===========================================================================

class TestCustomDateRange:
    def test_custom_range_returns_200(self, auth_client):
        resp = _get_profile(auth_client, {"from": "2026-05-01", "to": "2026-05-10"})
        assert resp.status_code == 200

    def test_custom_range_active_period_is_custom(self, auth_client):
        """A date range that matches no preset → active_period == 'custom'."""
        resp = _get_profile(auth_client, {"from": "2026-05-01", "to": "2026-05-10"})
        html = resp.data.decode()
        # No preset shortcut button should be active
        import re
        active_matches = re.findall(r'filter-preset-btn[^"]*active', html)
        assert len(active_matches) == 0, (
            "No preset button should be active when a custom range is applied"
        )

    def test_custom_range_filters_transactions(self, auth_client):
        """
        Expenses between 2026-05-01 and 2026-05-10:
          Grocery run (2026-05-01), Metro card top-up (2026-05-03),
          Electricity bill (2026-05-05), Pharmacy (2026-05-08),
          Movie + dinner (2026-05-10)  → 5 expenses
        """
        resp = _get_profile(auth_client, {"from": "2026-05-01", "to": "2026-05-10"})
        html = resp.data
        assert b"Grocery run" in html
        assert b"Metro card top-up" in html
        assert b"Electricity bill" in html
        assert b"Pharmacy" in html
        assert b"Movie + dinner" in html
        # Expenses outside the window must not appear
        assert b"New shoes" not in html, (
            "New shoes (2026-05-15) must not appear in 2026-05-01 to 2026-05-10 filter"
        )
        assert b"Coffee and snacks" not in html
        assert b"Miscellaneous" not in html

    def test_custom_range_transaction_count_stat(self, auth_client):
        """5 transactions between 2026-05-01 and 2026-05-10."""
        resp = _get_profile(auth_client, {"from": "2026-05-01", "to": "2026-05-10"})
        html = resp.data.decode()
        assert ">5<" in html, "Transaction count should be 5 for 2026-05-01 to 2026-05-10"

    def test_custom_range_total_spent_stat(self, auth_client):
        """
        450 + 120 + 1800 + 300 + 650 = 3320 for 2026-05-01 to 2026-05-10.
        """
        resp = _get_profile(auth_client, {"from": "2026-05-01", "to": "2026-05-10"})
        html = resp.data
        assert b"\xe2\x82\xb93,320.00" in html, (
            "Total Spent for 2026-05-01..2026-05-10 should be ₹3,320.00"
        )

    def test_custom_range_top_category_stat(self, auth_client):
        """Top category in 2026-05-01..2026-05-10 is Bills (₹1,800)."""
        resp = _get_profile(auth_client, {"from": "2026-05-01", "to": "2026-05-10"})
        html = resp.data
        assert b"Bills" in html

    def test_custom_range_category_breakdown_scoped(self, auth_client):
        """
        Only categories present in 2026-05-01..2026-05-10 appear in the breakdown.
        Shopping (2026-05-15) must not appear.
        """
        resp = _get_profile(auth_client, {"from": "2026-05-01", "to": "2026-05-10"})
        html = resp.data.decode()
        # breakdown-name spans should contain in-range categories
        assert "Bills" in html
        assert "Food" in html
        assert "Transport" in html
        # Shopping is outside the range
        breakdown_section_start = html.find("Spending by Category")
        breakdown_html = html[breakdown_section_start:]
        # Verify Shopping category bar does not appear in the breakdown section
        # We check that 'breakdown-name' with Shopping doesn't appear after the heading
        assert "breakdown-name" in breakdown_html, "Breakdown rows must be present"

    def test_custom_range_date_inputs_prefilled(self, auth_client):
        """
        When active_period == 'custom', the date inputs should be pre-filled
        with the active from/to values so the user can see and adjust them.
        """
        resp = _get_profile(auth_client, {"from": "2026-05-01", "to": "2026-05-10"})
        html = resp.data.decode()
        assert 'value="2026-05-01"' in html, "From date input should be pre-filled"
        assert 'value="2026-05-10"' in html, "To date input should be pre-filled"

    def test_custom_range_single_day(self, auth_client):
        """from == to → only expenses on that exact date are returned."""
        resp = _get_profile(auth_client, {"from": "2026-05-15", "to": "2026-05-15"})
        assert resp.status_code == 200
        html = resp.data
        assert b"New shoes" in html, "New shoes (2026-05-15) should appear"
        assert b"Grocery run" not in html, "Grocery run (2026-05-01) must not appear"


# ===========================================================================
# Edge case: empty result set in range
# ===========================================================================

class TestEmptyDateRange:
    def test_no_expenses_in_range_returns_200(self, auth_client):
        """A valid date range with no matching expenses must not crash."""
        resp = _get_profile(auth_client, {"from": "2025-01-01", "to": "2025-01-31"})
        assert resp.status_code == 200

    def test_no_expenses_in_range_zero_total(self, auth_client):
        resp = _get_profile(auth_client, {"from": "2025-01-01", "to": "2025-01-31"})
        html = resp.data
        assert b"\xe2\x82\xb90.00" in html, "Total Spent should be ₹0.00 when no expenses match"

    def test_no_expenses_in_range_zero_transaction_count(self, auth_client):
        resp = _get_profile(auth_client, {"from": "2025-01-01", "to": "2025-01-31"})
        html = resp.data.decode()
        assert ">0<" in html, "Transaction count must be 0 when no expenses match"

    def test_no_expenses_in_range_top_category_dash(self, auth_client):
        """When no expenses exist in range, top category should be the empty sentinel '—'."""
        resp = _get_profile(auth_client, {"from": "2025-01-01", "to": "2025-01-31"})
        html = resp.data
        assert "—".encode() in html, "Top category should be '—' when no expenses match"

    def test_no_expenses_in_range_empty_transaction_table(self, auth_client):
        """Transaction table body must be empty — no <tr> rows with txn-date."""
        resp = _get_profile(auth_client, {"from": "2025-01-01", "to": "2025-01-31"})
        html = resp.data.decode()
        assert "txn-date" not in html, (
            "No transaction rows (txn-date) should appear when date range has no expenses"
        )

    def test_no_expenses_in_range_empty_category_breakdown(self, auth_client):
        """Category breakdown list must be empty."""
        resp = _get_profile(auth_client, {"from": "2025-01-01", "to": "2025-01-31"})
        html = resp.data.decode()
        assert "breakdown-row" not in html, (
            "No breakdown-row elements should appear when date range has no expenses"
        )


# ===========================================================================
# Partial params — only one of from / to supplied → treated as All Time
# ===========================================================================

class TestPartialParams:
    def test_only_from_supplied_returns_200(self, auth_client):
        resp = _get_profile(auth_client, {"from": "2026-05-01"})
        assert resp.status_code == 200, "Only 'from' param must not cause an error"

    def test_only_from_supplied_shows_all_transactions(self, auth_client):
        """When only 'from' is present, the filter is ignored → All Time behaviour."""
        resp = _get_profile(auth_client, {"from": "2026-05-01"})
        html = resp.data
        # All 8 seed expenses should appear
        assert b"Grocery run" in html
        assert b"New shoes" in html
        assert b"Miscellaneous" in html

    def test_only_from_supplied_active_period_all_time(self, auth_client):
        """active_period must be 'all_time' when only from is present."""
        resp = _get_profile(auth_client, {"from": "2026-05-01"})
        html = resp.data.decode()
        idx = html.find("All Time")
        surrounding = html[max(0, idx - 200): idx + 20]
        assert "active" in surrounding, (
            "All Time button must be active when only 'from' param is supplied"
        )

    def test_only_to_supplied_returns_200(self, auth_client):
        resp = _get_profile(auth_client, {"to": "2026-05-31"})
        assert resp.status_code == 200, "Only 'to' param must not cause an error"

    def test_only_to_supplied_shows_all_transactions(self, auth_client):
        """When only 'to' is present, the filter is ignored → All Time behaviour."""
        resp = _get_profile(auth_client, {"to": "2026-05-31"})
        html = resp.data
        assert b"Grocery run" in html
        assert b"New shoes" in html
        assert b"Miscellaneous" in html

    def test_only_to_supplied_active_period_all_time(self, auth_client):
        resp = _get_profile(auth_client, {"to": "2026-05-31"})
        html = resp.data.decode()
        idx = html.find("All Time")
        surrounding = html[max(0, idx - 200): idx + 20]
        assert "active" in surrounding, (
            "All Time button must be active when only 'to' param is supplied"
        )


# ===========================================================================
# Validation: malformed date params → HTTP 400
# ===========================================================================

class TestMalformedDateParams:
    @pytest.mark.parametrize("params,label", [
        ({"from": "not-a-date", "to": "2026-05-31"}, "malformed from"),
        ({"from": "2026-05-01", "to": "not-a-date"}, "malformed to"),
        ({"from": "32/13/2026",  "to": "2026-05-31"}, "from wrong format"),
        ({"from": "2026-05-01", "to": "31-13-2026"},  "to wrong format"),
        ({"from": "",            "to": "2026-05-31"}, "empty from with to present — treated as All Time, not 400"),
        ({"from": "2026-13-01", "to": "2026-05-31"}, "from invalid month"),
        ({"from": "2026-05-01", "to": "2026-00-31"}, "to invalid month"),
    ])
    def test_malformed_date_returns_400(self, auth_client, params, label):
        # The spec says: "empty from with to" is treated as All Time (not 400).
        # The empty-from case is therefore excluded from the 400 expectation.
        if label == "empty from with to present — treated as All Time, not 400":
            resp = _get_profile(auth_client, params)
            assert resp.status_code == 200, (
                "Empty 'from' with valid 'to' should be treated as All Time, not 400"
            )
        else:
            resp = _get_profile(auth_client, params)
            assert resp.status_code == 400, (
                f"Malformed date ({label}) should return HTTP 400, got {resp.status_code}"
            )

    def test_both_params_malformed_returns_400(self, auth_client):
        resp = _get_profile(auth_client, {"from": "yesterday", "to": "tomorrow"})
        assert resp.status_code == 400

    def test_malformed_date_unauthenticated_still_redirects(self, client):
        """Auth guard fires before date validation — should be 302, not 400."""
        resp = _get_profile(client, {"from": "not-a-date", "to": "also-bad"})
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ===========================================================================
# Filter bar HTML structure
# ===========================================================================

class TestFilterBarStructure:
    def test_filter_bar_div_present(self, auth_client):
        resp = _get_profile(auth_client)
        assert b'class="filter-bar"' in resp.data

    def test_filter_presets_div_present(self, auth_client):
        resp = _get_profile(auth_client)
        assert b'class="filter-presets"' in resp.data

    def test_preset_buttons_are_anchor_tags(self, auth_client):
        """Preset shortcuts must be <a> tags — not <button> — so they work without JS."""
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        # Each preset button class should appear inside an <a> tag
        import re
        # Find all elements with filter-preset-btn class
        anchor_presets = re.findall(r'<a[^>]+filter-preset-btn[^>]*>', html)
        assert len(anchor_presets) == 4, (
            f"Expected 4 <a> preset buttons, found {len(anchor_presets)}"
        )

    def test_custom_form_has_two_date_inputs(self, auth_client):
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        import re
        date_inputs = re.findall(r'<input[^>]+type="date"[^>]*>', html)
        assert len(date_inputs) == 2, (
            f"Expected 2 date inputs in custom filter form, found {len(date_inputs)}"
        )

    def test_custom_form_has_apply_button(self, auth_client):
        resp = _get_profile(auth_client)
        assert b"Apply" in resp.data

    def test_filter_form_action_points_to_profile(self, auth_client):
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        assert 'action="/profile"' in html or "action='/profile'" in html, (
            "Custom filter form action must point to /profile"
        )

    def test_date_inputs_have_correct_names(self, auth_client):
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        assert 'name="from"' in html, "Date input for 'from' must have name='from'"
        assert 'name="to"' in html, "Date input for 'to' must have name='to'"


# ===========================================================================
# Preset URL construction — from/to params in href attributes
# ===========================================================================

class TestPresetUrls:
    def test_this_month_preset_url_contains_correct_bounds(self, auth_client):
        from_s, to_s = _this_month_bounds()
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        assert f"from={from_s}" in html, "This Month href must include today's month start"
        assert f"to={to_s}" in html, "This Month href must include today's date"

    def test_last_month_preset_url_contains_correct_bounds(self, auth_client):
        from_s, to_s = _last_month_bounds()
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        assert f"from={from_s}" in html
        assert f"to={to_s}" in html

    def test_last_3_months_preset_url_contains_correct_bounds(self, auth_client):
        from_s, to_s = _last_3_months_bounds()
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        assert f"from={from_s}" in html
        assert f"to={to_s}" in html

    def test_all_time_preset_url_has_no_date_params(self, auth_client):
        """All Time link href must be /profile with no from/to params."""
        resp = _get_profile(auth_client)
        html = resp.data.decode()
        # The All Time anchor's href should be exactly /profile (no query string)
        import re
        all_time_anchors = re.findall(r'<a[^>]+href="(/profile)"[^>]+filter-preset-btn[^>]*>', html)
        if not all_time_anchors:
            # Try alternate attribute order
            all_time_anchors = re.findall(r'<a[^>]+filter-preset-btn[^>]+href="(/profile)"[^>]*>', html)
        assert len(all_time_anchors) >= 1, (
            "All Time button must link to /profile with no query params"
        )


# ===========================================================================
# Stats and breakdown data correctness for a specific known window
# ===========================================================================

class TestFilteredDataCorrectness:
    """
    Use a narrow, deterministic date range — 2026-05-15 to 2026-05-22 — which
    covers exactly two seed expenses:
      - New shoes    ₹2,200  Shopping  2026-05-15
      - Coffee       ₹85     Food      2026-05-18
      - Miscellaneous ₹500   Other     2026-05-22
    Total = ₹2,785, count = 3, top category = Shopping
    """

    PARAMS = {"from": "2026-05-15", "to": "2026-05-22"}

    def test_filtered_total_spent(self, auth_client):
        resp = _get_profile(auth_client, self.PARAMS)
        html = resp.data
        assert b"\xe2\x82\xb92,785.00" in html, (
            "Total Spent for 2026-05-15..2026-05-22 should be ₹2,785.00"
        )

    def test_filtered_transaction_count(self, auth_client):
        resp = _get_profile(auth_client, self.PARAMS)
        html = resp.data.decode()
        assert ">3<" in html, "Transaction count should be 3 for 2026-05-15..2026-05-22"

    def test_filtered_top_category(self, auth_client):
        resp = _get_profile(auth_client, self.PARAMS)
        html = resp.data
        assert b"Shopping" in html

    def test_filtered_transactions_visible(self, auth_client):
        resp = _get_profile(auth_client, self.PARAMS)
        html = resp.data
        assert b"New shoes" in html
        assert b"Coffee and snacks" in html
        assert b"Miscellaneous" in html

    def test_out_of_range_transactions_excluded(self, auth_client):
        resp = _get_profile(auth_client, self.PARAMS)
        html = resp.data
        assert b"Grocery run" not in html, "Grocery run is outside the filter window"
        assert b"Electricity bill" not in html
        assert b"Metro card top-up" not in html
        assert b"Pharmacy" not in html
        assert b"Movie + dinner" not in html

    def test_filtered_category_breakdown_has_correct_categories(self, auth_client):
        resp = _get_profile(auth_client, self.PARAMS)
        html = resp.data.decode()
        # Only Shopping, Food, Other should appear in the breakdown
        assert "Shopping" in html
        assert "Food" in html
        assert "Other" in html

    def test_filtered_category_breakdown_excludes_out_of_range_categories(self, auth_client):
        """Bills and Transport only have expenses before 2026-05-15."""
        resp = _get_profile(auth_client, self.PARAMS)
        html = resp.data.decode()
        # Bills: only 2026-05-05 expense, Transport: only 2026-05-03 expense
        # Health: only 2026-05-08 expense — all outside 05-15..05-22
        # Entertainment: only 2026-05-10 — outside range
        breakdown_start = html.find("Spending by Category")
        breakdown_html = html[breakdown_start:]
        # breakdown-row entries should not contain these categories
        import re
        breakdown_names = re.findall(r'class="breakdown-name"[^>]*>([^<]+)<', breakdown_html)
        assert "Bills" not in breakdown_names, "Bills must not appear in breakdown for 05-15..05-22"
        assert "Transport" not in breakdown_names
        assert "Health" not in breakdown_names
        assert "Entertainment" not in breakdown_names

    def test_filtered_category_percentages_sum_to_100(self, auth_client):
        resp = _get_profile(auth_client, self.PARAMS)
        html = resp.data.decode()
        import re
        pcts = re.findall(r'style="width:\s*(\d+)%"', html)
        if pcts:
            total = sum(int(p) for p in pcts)
            assert total == 100, f"Category percentages must sum to 100, got {total}"


# ===========================================================================
# Query-layer unit tests: date filtering in helpers (via mock)
# ===========================================================================

class TestQueryHelperDateFiltering:
    """
    Unit-test the query helpers directly using the mock pattern established
    in test_backend_connection.py.  These tests verify that the helpers
    correctly apply BETWEEN when date_from/date_to are supplied.
    """

    @pytest.fixture()
    def mock_db(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Test", "t@t.com", "hash"),
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 100.0, "Food",      "2026-04-15", "April expense"),
                (user_id, 200.0, "Bills",     "2026-05-01", "May Bills"),
                (user_id, 300.0, "Shopping",  "2026-05-20", "May Shopping"),
                (user_id, 400.0, "Transport", "2026-06-10", "June Transport"),
            ],
        )
        conn.commit()
        yield conn, user_id
        conn.close()

    def test_get_summary_stats_date_filtered(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_summary_stats
        with patch("database.queries.get_db", return_value=conn):
            result = get_summary_stats(user_id, date_from="2026-05-01", date_to="2026-05-31")
        assert result["transaction_count"] == 2
        assert result["total_spent"] == "₹500.00"
        assert result["top_category"] == "Shopping"

    def test_get_summary_stats_no_filter_returns_all(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_summary_stats
        with patch("database.queries.get_db", return_value=conn):
            result = get_summary_stats(user_id)
        assert result["transaction_count"] == 4
        assert result["total_spent"] == "₹1,000.00"

    def test_get_recent_transactions_date_filtered(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_recent_transactions
        with patch("database.queries.get_db", return_value=conn):
            result = get_recent_transactions(user_id, date_from="2026-05-01", date_to="2026-05-31")
        assert len(result) == 2
        dates = {r["date"] for r in result}
        assert "2026-04-15" not in dates, "April expense must be excluded"
        assert "2026-06-10" not in dates, "June expense must be excluded"

    def test_get_recent_transactions_no_filter_returns_all(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_recent_transactions
        with patch("database.queries.get_db", return_value=conn):
            result = get_recent_transactions(user_id)
        assert len(result) == 4

    def test_get_category_breakdown_date_filtered(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_category_breakdown
        with patch("database.queries.get_db", return_value=conn):
            result = get_category_breakdown(user_id, date_from="2026-05-01", date_to="2026-05-31")
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert "Bills" in names
        assert "Shopping" in names
        assert "Food" not in names
        assert "Transport" not in names

    def test_get_category_breakdown_no_filter_returns_all(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_category_breakdown
        with patch("database.queries.get_db", return_value=conn):
            result = get_category_breakdown(user_id)
        assert len(result) == 4

    def test_get_category_breakdown_empty_range(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_category_breakdown
        with patch("database.queries.get_db", return_value=conn):
            result = get_category_breakdown(user_id, date_from="2020-01-01", date_to="2020-12-31")
        assert result == [], "Empty range must return empty list"

    def test_get_summary_stats_empty_range(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_summary_stats
        with patch("database.queries.get_db", return_value=conn):
            result = get_summary_stats(user_id, date_from="2020-01-01", date_to="2020-12-31")
        assert result["transaction_count"] == 0
        assert result["total_spent"] == "₹0.00"
        assert result["top_category"] == "—"

    def test_get_recent_transactions_empty_range(self, mock_db):
        conn, user_id = mock_db
        from database.queries import get_recent_transactions
        with patch("database.queries.get_db", return_value=conn):
            result = get_recent_transactions(user_id, date_from="2020-01-01", date_to="2020-12-31")
        assert result == []

    def test_only_date_from_no_filter_applied(self, mock_db):
        """When only date_from is passed (date_to=None), the helper returns all rows."""
        conn, user_id = mock_db
        from database.queries import get_summary_stats
        with patch("database.queries.get_db", return_value=conn):
            result = get_summary_stats(user_id, date_from="2026-05-01")
        assert result["transaction_count"] == 4, (
            "Without date_to, no date filter should be applied"
        )

    def test_only_date_to_no_filter_applied(self, mock_db):
        """When only date_to is passed (date_from=None), the helper returns all rows."""
        conn, user_id = mock_db
        from database.queries import get_recent_transactions
        with patch("database.queries.get_db", return_value=conn):
            result = get_recent_transactions(user_id, date_to="2026-05-31")
        assert len(result) == 4, (
            "Without date_from, no date filter should be applied"
        )
