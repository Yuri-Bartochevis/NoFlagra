# NO FLAGRA — cloud app

The multi-tenant half of the product: accounts, establishments (gyms), and
(from Phase 4 on) the clip library. Serves the public marketing site and the
authenticated dashboard from one Flask app. See the root
[README's "Where this is going"](../README.md#where-this-is-going--no-flagra-as-a-product)
section for the full architecture and phase plan — this file is just local
dev setup.

**Phase 1 status:** the public landing page is real, and so is signup/login —
`User`, `Establishment`, and `Membership` are live tables, "Start your gym"
creates a real account, and `/app/*` is gated by a real session and scoped to
the logged-in user's establishment. Not built yet: invites (adding a second
person to a gym) and device pairing — those come next.

## Run it

```
docker compose up -d --build
flask db upgrade   # see "Migrations" below — needed once, on a fresh db
curl http://localhost:8000/health
```

Then open <http://localhost:8000> — the real landing page, with a working
"Start your gym" signup.

(Use `docker compose`, the space-separated v2 form — Compose V1's
`docker-compose` doesn't understand this file's syntax.)

`db` is a throwaway local Postgres (`postgres:16-alpine`), not meant to hold
anything you care about yet. Tear it down with `docker compose down`; add
`-v` to also drop the volume and start clean.

## Migrations

Schema changes go through Flask-Migrate/Alembic, checked into `migrations/`.

```
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export FLASK_APP=wsgi.py
export DATABASE_URL=postgresql://noflagra:noflagra@localhost:5432/noflagra  # needs `docker compose up -d db` first
flask db upgrade                 # apply migrations to a fresh db
flask db migrate -m "message"    # after changing app/models.py
```

## Run it without Docker

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point DATABASE_URL at a Postgres you already have running
export FLASK_APP=wsgi.py
flask db upgrade
python3 -c "from app import create_app; create_app().run(debug=True, port=8000)"
```

## Running the tests

Uses a throwaway SQLite file per test, no Postgres or Docker needed.

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -v
```

Expect `12 passed` — landing page, health check, signup (including the admin
membership it creates, duplicate-email/short-password rejection), login/logout,
dashboard gating, and that two gyms can't see each other's establishment.

## Layout

```
cloud/
├── app/
│   ├── __init__.py          create_app() factory
│   ├── extensions.py        shared Flask extensions (db, login_manager, migrate)
│   ├── models.py            User, Establishment, Membership, Invite, Device, Clip
│   ├── templates/           base.html + landing page, signup, login, dashboard placeholder
│   └── blueprints/
│       ├── public.py        public_bp — / (landing page) and /health
│       ├── auth.py          auth_bp — /signup, /login, /logout
│       └── dashboard.py     dashboard_bp — /app/*, gated + establishment-scoped
├── migrations/               Alembic, via Flask-Migrate — commit these
├── test_app.py
├── wsgi.py                  gunicorn entrypoint
├── requirements.txt
├── Dockerfile                multi-worker (unlike the edge app) — sessions
│                              are stateless signed cookies, no in-process
│                              state to worry about
└── docker-compose.yml        this app + a local Postgres for dev
```
