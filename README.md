# NO FLAGRA

*(formerly "Gym Instant Replay" — same project, now aimed at more than one gym)*

A physical button beside a jiu-jitsu mat that saves the **last 10 minutes** of
footage as a video clip.

Today that's the whole system: one gym, one Raspberry-Pi-to-be, one shared
secret, clips on local disk (its full setup docs now live in
[`edge/README.md`](edge/README.md)). It keeps working exactly as it always
has — it's becoming the **edge** half of a larger product. See
[Where this is going](#where-this-is-going--no-flagra-as-a-product) below for
the multi-gym architecture this is evolving into.

---

## How it works (the one idea worth understanding)

Frigate records the mat camera **continuously**, 24/7, onto your hard drive —
like a tape that never stops rolling.

When you press the button, nothing starts recording. Instead the button says to
Frigate: *"take the tape and cut out the last 10 minutes as a separate file."*

That's the whole trick. **The footage already exists before you press.** The
button is a pair of scissors, not a camera.

```
[Button] --wired--> [ESP32, Wi-Fi]
                          |  HTTP POST /save-clip
                          v
                  [Receiver, port 5001]
                          |  "export from (now - 10 min) to (now + 15s)"
                          v
                  [Frigate, port 5000]  <--RTSP--  [Camera]
                          |
                          v
                  edge/storage/exports/mat_2026-07-19_14-32-05.mp4
```

Two consequences worth remembering:

- Frigate must have been running for at least 10 minutes before a press can
  produce a full clip. No tape, nothing to cut.
- A few seconds of delay anywhere in the chain costs you nothing, because the
  clip is retroactive. This matters later for battery life.

---

## Repo layout

Two halves, each with its own setup docs:

| | |
|---|---|
| [`edge/`](edge/README.md) | Frigate + receiver + ESP32 firmware — what runs at the gym. Full setup, hardware notes, and troubleshooting live there. |
| [`cloud/`](cloud/README.md) | The multi-tenant Flask app: accounts, establishments, and (from Phase 4) the clip library and public marketing site. |

If you're setting up a gym's camera and button, go to
**[`edge/README.md`](edge/README.md)** — that's the whole story for today's
system. Keep reading here for where the product is headed.

---

## Where this is going — NO FLAGRA as a product

Today this repo runs **one** gym. The plan is to let any gym or academy sign
up, keep running its own camera + Pi locally, and get a login to a shared
cloud dashboard — modeled loosely on
[replaysports.com.br](https://www.replaysports.com.br), branded black + a
strong yellow (`#FFD400`), heavy display type (Anton), the identity already
built into the dashboard in `edge/receiver/templates/index.html`.

### The split: edge vs. cloud

The current `receiver/` + `frigate/` + `firmware/` don't get rebuilt — they
get a narrower job. A new cloud app takes over everything involving accounts,
tenants, and the clip library:

```
                          ┌───────────────────────────────────────────┐
                          │             cloud app (Flask)              │
      any browser ──────▶ │  public_bp   /             marketing site  │
                          │  app_bp      /app/*   post-login dashboard │
                          │                                             │
                          │  Postgres:  User · Establishment ·         │
                          │             Membership · Invite ·          │
                          │             Device · Clip                  │
                          └───────────┬─────────────────┬───────────────┘
                                      │ presigned S3      │ device API key
                                      │ PUT / GET          │ (pairing code)
                                      ▼                    ▼
                              ┌───────────────┐    ┌───────────────────┐
                              │  S3 bucket     │    │  Gym A — edge Pi   │
                              │  (video clips, │◀───│  Frigate + receiver│◀── button (ESP32)
                              │  prefixed per   │    └───────────────────┘
                              │  establishment) │    ┌───────────────────┐
                              │                │◀───│  Gym B — edge Pi   │
                              └───────────────┘    │  Frigate + receiver│◀── button (ESP32)
                                                     └───────────────────┘
```

Each gym's Pi is paired to its own `Establishment` with a device key (no more
one global shared secret) and, after every export, uploads the clip straight
to S3 via a presigned URL the cloud app hands out. The Pi never holds AWS
credentials. Live view stays LAN-only for now — the cloud dashboard shows
"live view available on the gym's own network" rather than pulling in a video
relay that isn't needed to sell the clip library.

### Data model (cloud side, new)

| Table | What it holds |
|---|---|
| `User` | email, password hash, name |
| `Establishment` | the tenant — one per gym |
| `Membership` | user ⇄ establishment, with a role (`admin` / `member`) |
| `Invite` | pending email invites into an establishment |
| `Device` | a paired Raspberry Pi — UUID, establishment (one device per account, for now), hashed device key |
| `Camera` | one row per camera a device drives — a device can have several |
| `Clip` | camera, establishment, S3 key, timestamps, size, status — replaces today's `os.listdir()` directory scan |

`Establishment → Device → Camera → Clip` is one gym's account owning one Pi
driving several cameras, each producing its own clips. Full design —
pairing (script-based, no UI yet), the device-facing API, and the S3 key
layout — is in [`docs/infrastructure.md`](docs/infrastructure.md).

### Landing page sketch (`/`, public, no login)

```
┌──────────────────────────────────────────────────────────┐
│  ⚡ NO FLAGRA                                  [ Log in ] │  black bg, yellow wordmark
├──────────────────────────────────────────────────────────┤
│                                                            │
│        NEVER MISS THE MOMENT.                             │  Anton, huge, yellow on black
│        Press a button mat-side. Get the last               │
│        10 minutes, saved and ready to watch.               │
│                                                            │
│                 [ START YOUR GYM ]   ← yellow CTA          │
│                                                            │
├──────────────────────────────────────────────────────────┤
│  HOW IT WORKS                                              │
│   1. PRESS       2. CUT          3. REVIEW      4. SHARE   │
│   the button     from the        on your        with your  │
│                  rolling tape    phone          team        │
├──────────────────────────────────────────────────────────┤
│  WHY GYMS USE IT                                            │
│  [Never miss a] [One button,  ] [Everyone on ] [Cloud clip] │
│  [submission   ] [no camera   ] [the mat, one] [library,   ] │
│  [again        ] [operator    ] [login       ] [full history]│
├──────────────────────────────────────────────────────────┤
│  SEE IT IN ACTION                                            │
│    [ screenshot of the real black/yellow dashboard ]         │
├──────────────────────────────────────────────────────────┤
│  Ready to put one on your mat?        [ START YOUR GYM ]     │
├──────────────────────────────────────────────────────────┤
│  © NO FLAGRA · contact · github                               │
└──────────────────────────────────────────────────────────┘
```

### Route map (post-login app lives at `/app/*`)

```
/                 public marketing site (no login)      — done
/features, /about  more marketing pages                  — Phase 5
/signup             "Start your gym" — creates User +
                     Establishment + Membership(admin)    — done
/login, /logout      session login                        — done
/invite/<token>       accept an invite, set a password     — done

/app/                gated + establishment-scoped,          — done (placeholder),
                      placeholder today; Phase 4 replaces      Phase 4 for real content
                      it with the real black/yellow
                      dashboard:
                        - live view (LAN-only banner if
                          viewed off the gym's network)
                        - clip library, from Postgres +
                          presigned S3 URLs
(pairing is a script,        an admin runs a CLI script to      — Phase 2
 not a route yet)             pair a device — see
                               docs/infrastructure.md
/app/team               admin: invite/manage members          — done
```

### Build order

Each phase leaves the system working end to end; the existing gym keeps
running throughout.

0. **Scaffolding** *(done)* — split into `edge/` (today's `receiver/`,
   `frigate/`, `firmware/`, unchanged behavior) and `cloud/` (new Flask +
   Postgres app, `public_bp` + a `/health` route proving DB connectivity —
   see [`cloud/README.md`](cloud/README.md)).
1. **Cloud identity & tenancy** *(app built)* — schema, login, "Start your
   gym" signup, and the admin invite flow are all live. Still open: actually
   migrating the real gym's account through this flow, and emailing invite
   links instead of the admin copying them from a flash message.
2. **Device pairing + clip metadata** *(done)* — pairing is a pair of CLI
   scripts (`cloud/scripts/create_pairing_code.py` and
   `edge/tools/pair_device.py`) talking to a device-facing API, not a
   dashboard page; one device (UUID-identified) per account, many cameras per
   device. The receiver posts clip metadata after each export, best effort,
   so a cloud outage never affects recording; an unpaired Pi behaves exactly
   as it did before the cloud existed. Playback still points at the Pi's LAN
   address. Full design in [`docs/infrastructure.md`](docs/infrastructure.md).
   Known gap carried into Phase 3: `size_bytes` is posted as 0, because
   Frigate exports asynchronously and the file doesn't exist yet when the
   export API returns — the uploader fills in the real size.
3. **S3 upload pipeline** — presigned PUT/GET URLs, a durable upload-retry
   queue on the Pi (survives a reboot mid-upload).
4. **Ship the branded post-login app** — the dashboard moves to `/app`,
   scoped by establishment; the Pi's old browser-facing routes are retired.
5. **Public marketing site** — the landing page above, wired to signup.
6. **Second tenant onboarding** — pair a second Pi under a new
   establishment, invite a second admin, verify gym A can't see gym B's
   clips, settle an S3 retention policy.

Deliberately out of scope for now: remote WebRTC live view, billing/plan
tiers, multi-camera-per-gym, a mobile app, per-gym subdomains.

---

## Status

- [x] Frigate config (0.17 schema, continuous recording)
- [x] Receiver built around Frigate's export API, tests passing
- [x] ESP32 firmware written (edge-triggered, LED feedback)
- [x] End-to-end verified with the simulated camera
- [x] Dashboard restyled to the NO FLAGRA black/yellow identity
- [x] Repo split into `edge/` and `cloud/`, cloud app scaffold reaches Postgres (Phase 0)
- [ ] Real camera streaming into Frigate
- [ ] Real button, end to end
- [ ] Deep sleep for battery life
- [ ] Moved to the Raspberry Pi
- [x] Public marketing site live at `/` — hero, how-it-works, benefits, showcase, CTA (Phase 5, pulled forward)
- [x] Signup/login/logout, `Establishment` + admin `Membership`, `/app` gated and tenant-scoped (Phase 1)
- [x] Admin invite flow — invite by email/role, accept/revoke/expire, existing-account password check (Phase 1)
- [x] Selling funnel (landing/signup/login) defaults to PT-BR, EN as a toggle
- [x] Device pairing (UUID + hashed key, script-driven) and clip metadata posted to the cloud after each export (Phase 2)
- [ ] S3 upload pipeline (Phase 3)
- [ ] Post-login dashboard replaced with the real black/yellow clip library (Phase 4)
- [ ] Second gym onboarded (Phase 6)
