# NO FLAGRA — cloud app

The multi-tenant half of the product: accounts, establishments (gyms), and
(from Phase 4 on) the clip library. Serves the public marketing site and the
authenticated dashboard from one Flask app. See the root
[README's "Where this is going"](../README.md#where-this-is-going--no-flagra-as-a-product)
section for the full architecture and phase plan — this file is just local
dev setup.

Right now (Phase 0) this is scaffolding: an app factory, one blueprint, and a
`/health` route that proves the app can reach Postgres. No accounts, no
schema yet — that's Phase 1.

## Run it

```
docker compose up -d --build
curl http://localhost:8000/health
```

(Use `docker compose`, the space-separated v2 form — Compose V1's
`docker-compose` doesn't understand this file's syntax.)

`db` is a throwaway local Postgres (`postgres:16-alpine`), not meant to hold
anything you care about yet. Tear it down with `docker compose down`; add
`-v` to also drop the volume and start clean.

## Run it without Docker

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point DATABASE_URL at a Postgres you already have running
python3 -c "from app import create_app; create_app().run(debug=True, port=8000)"
```

## Layout

```
cloud/
├── app/
│   ├── __init__.py          create_app() factory
│   ├── extensions.py        shared Flask extensions (db, ...)
│   └── blueprints/
│       └── public.py        public_bp — / and /health for now
├── wsgi.py                  gunicorn entrypoint
├── requirements.txt
├── Dockerfile                multi-worker (unlike the edge app) — sessions
│                              are stateless signed cookies, no in-process
│                              state to worry about
└── docker-compose.yml        this app + a local Postgres for dev
```
