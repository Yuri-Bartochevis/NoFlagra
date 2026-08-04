# NO FLAGRA — cloud app

The multi-tenant half of the product: accounts, establishments (gyms), and
(from Phase 4 on) the clip library. Serves the public marketing site and the
authenticated dashboard from one Flask app. See the root
[README's "Where this is going"](../README.md#where-this-is-going--no-flagra-as-a-product)
section for the full architecture and phase plan — this file is just local
dev setup.

**Phase 1 status:** the public landing page is real, signup/login work, and so
does the admin invite flow — `/app/team` lets an admin invite by email
(member or admin), the invite link goes to `/invite/<token>`, and accepting it
creates the account (or, for an email that already has a NO FLAGRA account
elsewhere, requires that account's real password before adding the
membership — an invite link alone never logs anyone in). Not built yet:
actually emailing the invite link (no mail provider wired up — the admin
copies it from a flash message today) and device pairing.

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

Expect `45 passed` — landing page (PT default + EN toggle), the `<html lang>`
attribute, description/canonical/`og:` social cards, the showcase video, the
about/privacy/terms pages and their English redirects, `robots.txt` and
`sitemap.xml`, health check,
signup (including the admin membership it creates, duplicate-email/
short-password rejection), login/logout, dashboard gating, tenant isolation,
and the invite flow: creating/revoking invites, admin-only enforcement,
duplicate/already-a-member rejection, a brand-new person accepting, an
existing user having to prove their password before joining a second gym,
and expired/revoked/already-accepted tokens all correctly refusing to work.

## Layout

```
cloud/
├── app/
│   ├── __init__.py          create_app() factory
│   ├── extensions.py        shared Flask extensions (db, login_manager, migrate)
│   ├── models.py            User, Establishment, Membership, Invite, Device, Clip
│   ├── i18n.py               PT/EN translation dict + locale helper
│   ├── storage.py           R2 (S3 API) — presigned upload/playback URLs
│   ├── templates/           base.html + landing page, signup, login, team,
│   │                         invite acceptance, dashboard placeholder
│   └── blueprints/
│       ├── public.py        public_bp — / (landing page) and /health
│       ├── auth.py          auth_bp — /signup, /login, /logout, /invite/<token>
│       ├── dashboard.py     dashboard_bp — /app/*, gated + establishment-scoped,
│       │                     including /app/team (admin invite management)
│       └── share.py         share_bp — /c/<token>, the public clip page
├── scripts/
│   ├── create_pairing_code.py
│   └── mock_r2.py           a fake R2 for local development
├── migrations/               Alembic, via Flask-Migrate — commit these
├── test_app.py
├── wsgi.py                  gunicorn entrypoint
├── requirements.txt
├── Dockerfile                multi-worker (unlike the edge app) — sessions
│                              are stateless signed cookies, no in-process
│                              state to worry about
└── docker-compose.yml        this app + a local Postgres for dev
```


---

## Clip storage (Phase 3)

Clips live in Cloudflare R2. Nothing is uploaded automatically — someone at the
gym picks a clip on the Pi's manage page and shares it. The continuous
recording never leaves the building.

### Why R2 rather than S3

Egress. S3 charges roughly $0.09/GB to send data out; R2 charges nothing. A
gym on the R$150/month plan whose clips get watched a few hundred times a day
would cost more in S3 bandwidth than it pays us — and it gets worse the more
its clips are shared, which is exactly the behaviour the product depends on.
R2 speaks the S3 API, so `app/storage.py` works against either: point
`R2_ENDPOINT` somewhere else and the code is unchanged.

### Configuration

```
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_BUCKET=noflagra
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_REGION=auto              # R2 has no regions; "auto" is what Cloudflare uses
UPLOAD_URL_TTL=3600         # a 300 MB clip on gym Wi-Fi needs the headroom
PLAYBACK_URL_TTL=3600
```

With those unset, everything else still works: clip metadata is recorded, and
the upload endpoints answer `503 object storage is not configured`.

### The upload handshake

The Pi never holds R2 credentials. It gets a URL that can write exactly one
object:

```
Pi                              cloud                        R2
 |  POST /api/clips              |                            |
 |  (idempotent on filename)     |                            |
 |----------------------------->|                            |
 |  POST /clips/<id>/upload-url  |                            |
 |----------------------------->|  presign PUT               |
 |<-----------------------------|                            |
 |  PUT <presigned url>  ------------------------------------>|
 |  POST /clips/<id>/uploaded    |                            |
 |----------------------------->|  HEAD (verify it landed)   |
 |<--- share_url ---------------|                            |
```

Two things this buys, both deliberate:

- **The bytes never pass through this app.** Streaming 300 MB through a web
  worker would occupy it for minutes, and the free tier has two.
- **The Pi's word is not evidence.** A clip only becomes `ready` after a HEAD
  confirms an object of non-zero size is actually in the bucket. A truncated
  PUT leaves a 0-byte object, and publishing a link to that would hand someone
  a video that plays nothing.

### The share page

`/c/<token>` — no login, no app. The token is random rather than the row id,
so nobody can walk the list of every clip every gym has shared. The page
points `<video>` at `/c/<token>/video`, which signs a fresh short-lived URL and
redirects on each request; a copied page link keeps working, while a storage
URL scraped out of it expires within the hour. Redirecting rather than proxying
is also what makes seeking work — the browser's range requests go straight to
R2.

### Developing without an R2 account

```
python scripts/mock_r2.py                    # :5002, files under ./r2-data
export R2_ENDPOINT=http://localhost:5002 R2_BUCKET=noflagra-dev
export R2_ACCESS_KEY_ID=dev R2_SECRET_ACCESS_KEY=dev
```

It ignores request signatures — verifying SigV4 there would be testing
botocore, not us — but stores, HEADs and serves with range support like the
real thing. It authenticates nobody, so keep it on your laptop.
