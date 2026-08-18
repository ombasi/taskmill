# Taskmill

Flask task-earning platform (Uganda-first, multi-currency ready).

## Stack
- Flask 3 + SQLAlchemy + Flask-Login + Flask-Migrate
- Jinja2 templates (glassmorphism UI)
- SQLite (local) / PostgreSQL (production via `DATABASE_URL`)

## Core business rules
1. **Membership-driven limits** – `tasks_per_set × daily_sets` define daily capacity.
2. **Set → Withdraw flow** – after each set the user must submit a withdrawal before the next set unlocks (skipped on negative trading days).
3. **Wallet** – all balance changes go through `WalletService` and create `WalletTransaction` rows.
4. **Currency** – `{{ money(user, amount) }}` formats UGX / KES / etc. No hardcoded `$`.
5. **Referrals** – bonus paid once when the referred user activates a paid membership path.

## Quick start (local)
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_APP=app.py
python seed.py              # creates tables + sample data
python app.py               # http://127.0.0.1:5000
```

Default admin: `admin` / `admin123`

## Environment
| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Session / CSRF secret (required in production) |
| `DATABASE_URL` | e.g. `postgresql+pg8000://user:pass@host/db` |

## Production (Gunicorn)
```bash
gunicorn -w 2 -b 0.0.0.0:8000 "app:create_app()"
```

On Render / Railway / similar: set `DATABASE_URL` and `SECRET_KEY`, run `python seed.py` once (or use migrations).

## Project layout
```
app.py              # factory
config.py
extensions.py
models/             # SQLAlchemy models
routes/             # blueprints
services/           # WalletService, TaskService, …
helpers/currency.py
utils/security.py   # CSRF helpers
templates/
static/
seed.py
```

## Memberships (seed defaults)
| Plan    | Price (UGX) | Tasks/set | Sets/day |
|---------|-------------|-----------|----------|
| Starter | 15,000      | 2         | 1        |
| Silver  | 60,000      | 2         | 3        |
| Gold    | 150,000     | 2         | 4        |
| VIP     | 350,000     | 2         | 5        |

## Status
Architecture cleaned, multi-set task enforcement, unified wallet, UGX currency, referrals, deposits/withdrawals with notifications, CSRF on critical forms. Ready for staging deploy and final QA.
