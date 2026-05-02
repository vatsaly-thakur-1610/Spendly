# Spec: Login and Logout

## Overview
This feature adds session-based authentication to Spendly. Users can log in with their email and password, and the app verifies credentials against the hashed password stored during registration. A successful login stores the user's ID in the Flask session, granting access to protected pages. Logout clears the session and redirects to the landing page. This is the foundation that all subsequent protected routes (profile, expenses) depend on.

## Depends on
- Step 01 — Database Setup (users table, `get_db()`)
- Step 02 — Registration (user records with hashed passwords via `create_user()`)

## Routes
- `POST /login` — validates email/password, sets session, redirects to `/profile` on success — public
- `GET /logout` — clears session, redirects to `/` — public (no login check needed)

## Database changes
Add one helper function to `database/db.py`:
- `get_user_by_email(email)` — queries users table by email, returns a single row or `None`

No new tables or columns required.

## Templates
- **Modify:** `templates/login.html` — add a `<form method="post" action="{{ url_for('login') }}">` block with email and password inputs; display flashed error messages; keep the existing layout

## Files to change
- `app.py` — add `POST /login` handler; replace stub `GET /logout` with a real implementation; import `session` from flask and `get_user_by_email` from db
- `database/db.py` — add `get_user_by_email(email)` helper
- `templates/login.html` — add POST form and flash message display

## Files to create
No new files.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already available via Flask.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Password verification with `werkzeug.security.check_password_hash` — never compare plaintext
- Session storage via Flask `session` — store only `user_id` (integer)
- Use `flash()` for all user-facing error messages — never return raw error strings
- Use `abort()` for unexpected HTTP errors, not bare string returns
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values
- The `GET /logout` route must call `session.clear()` (not `session.pop`) to wipe all session data
- On failed login, re-render `login.html` with a generic error ("Invalid email or password") — do not distinguish between wrong email and wrong password
- On successful login, redirect to `/profile` using `redirect(url_for('profile'))`
- Do not add a `@login_required` decorator in this step — that belongs in Step 4

## Definition of done
- [ ] Visiting `/login` renders the login form
- [ ] Submitting the form with a valid email and correct password redirects to `/profile`
- [ ] Submitting the form with a valid email but wrong password re-renders the login page with a flash error
- [ ] Submitting the form with an unknown email re-renders the login page with a flash error
- [ ] After a successful login, `session['user_id']` is set to the correct user's integer ID
- [ ] Visiting `/logout` clears the session and redirects to `/`
- [ ] After logout, `session.get('user_id')` returns `None`
- [ ] All form inputs use `url_for('login')` — no hardcoded URLs
