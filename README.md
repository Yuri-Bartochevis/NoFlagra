# NO FLAGRA

*(formerly "Gym Instant Replay" — same project, now aimed at more than one gym)*

A physical button beside a jiu-jitsu mat that saves the **last 10 minutes** of
footage as a video clip.

Everything below this point documents **today's system**: one gym, one
Raspberry-Pi-to-be, one shared secret, clips on local disk. That system keeps
working exactly as described — it's becoming the **edge** half of a larger
product. See [Where this is going](#where-this-is-going--no-flagra-as-a-product)
for the multi-gym architecture this is evolving into.

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
                  storage/exports/mat_2026-07-19_14-32-05.mp4
```

Two consequences worth remembering:

- Frigate must have been running for at least 10 minutes before a press can
  produce a full clip. No tape, nothing to cut.
- A few seconds of delay anywhere in the chain costs you nothing, because the
  clip is retroactive. This matters later for battery life.

---

## What's in the folder

| Path | What it is |
|---|---|
| `docker-compose.yml` | Defines the containers: Frigate, the receiver, and a fake test camera |
| `.env` | Your secret password (hidden file — see below) |
| `frigate/config.yml` | Frigate settings for the **real** camera |
| `frigate/config.sim.yml` | Same, but pointed at the **fake** test camera |
| `receiver/app.py` | The small server the button talks to |
| `receiver/test_app.py` | Automated tests |
| `tools/fake_button.py` | Pretends to be the button (optional — curl does the same) |
| `tools/mock_frigate.py` | Pretends to be Frigate, for testing the receiver alone |
| `firmware/button_trigger.ino` | The ESP32 sketch |
| `storage/` | Created automatically. Recordings and exported clips live here |

---

## Setup

### 0. Prerequisites

- **Docker Desktop** — from docker.com. Must be running (whale icon in the
  menu bar) before any command below will work.
- A terminal opened **in the project folder**. On Mac: right-click the folder →
  Services → "New Terminal at Folder".

> **Which Docker command do I type?**
> There are two variants in the wild: `docker-compose` (hyphen) and
> `docker compose` (space). Only one may exist on your machine. Find out with:
> ```
> docker-compose version
> ```
> If that prints a version number, use the **hyphenated** form everywhere in
> this README. If it says "not found", use the spaced form instead.
> This README uses the hyphen; substitute if yours differs.

### 1. Create your secret

```
cp .env.example .env
```

`.env` holds the password shared between the button and the receiver. It starts
with a placeholder value; change it to anything you like:

```
nano .env
```

Edit the line, then Ctrl+O, Enter, Ctrl+X to save and quit.

**Write this value down.** You'll paste the identical string into the ESP32
sketch later.

> **Why can't I see `.env` in Finder?**
> Files starting with a dot are hidden on Mac and Linux. Use `ls -la` to list
> them, `cat .env` to read one, or press Cmd+Shift+Period in Finder to toggle
> hidden files on and off.

### 2. Point Frigate at a camera

**For testing without hardware**, use the fake camera:

```
cp frigate/config.yml frigate/config.real.yml
cp frigate/config.sim.yml frigate/config.yml
```

(The first line parks the real config safely aside so you can restore it later.)

**For the real camera**, open `frigate/config.yml` and replace the `path:` line
with the RTSP address from the Mibo app. Percent-encode any special characters
in the password: `@` becomes `%40`, `#` becomes `%23`.

### 3. Start it

```
docker-compose up frigate receiver fakecam
```

Drop `fakecam` once you're on the real camera.

The first run downloads Frigate, which is a large image — expect several
minutes of scrolling text. Leave this terminal running; it *is* the system.
To run it in the background instead, add `-d`.

### 4. Check it's alive

Open <http://localhost:5000>. With the fake camera you should see a moving
colour-bar test pattern with a counter ticking upward. With the real camera,
you should see the mat.

Confirm all three containers are up:

```
docker-compose ps
```

---

## Triggering a clip with curl

`curl` is built into macOS and Linux — no Python needed. It sends exactly the
same request the ESP32 will send.

```
curl -X POST http://localhost:5001/save-clip -H "X-Auth-Token: YOUR_SECRET"
```

Replace `YOUR_SECRET` with the value from `.env` (run `cat .env` to see it).

**A successful press looks like:**

```json
{"clip":"mat_2026-07-19_14-32-05","lookback_seconds":600,"status":"accepted"}
```

**Other responses:**

| Response | Meaning | Fix |
|---|---|---|
| `{"error":"unauthorized"}` | Secret doesn't match | Check `cat .env`, copy it exactly |
| `{"status":"cooldown"}` | Pressed again too soon | Normal. Wait 30 seconds |
| `Connection refused` | Receiver isn't running | `docker-compose ps`, then `docker-compose up -d receiver` |

### Then find your clip

The receiver waits ~15 seconds before exporting, so the last few seconds of
video can be written to disk. After that:

**In the browser:** <http://localhost:5000> → **Export** in the menu. Play it —
with the fake camera, the counter should run from 10 minutes before your press
right up to it.

**On disk:**

```
ls -la storage/exports/
open storage/exports/
```

**In the logs:**

```
docker-compose logs receiver
```

Look for `Export requested:`. If you see `EXPORT FAILED`, the message after it
says why.

> **Testing impatiently:** a fresh Frigate has no footage yet, so a 10-minute
> request returns a short clip or nothing. Either wait 11 minutes, or edit
> `LOOKBACK_SECONDS: "600"` to `"60"` in `docker-compose.yml` and run
> `docker-compose up -d receiver`.

---

## The GYM REC dashboard (port 5001)

The page you actually use mat-side. Frigate on port 5000 is the engine room
underneath — visit it when something breaks, not day to day.

- **Live view** of the mat, refreshed every 2 seconds
- **One big save button**, which locks out and counts down during the cooldown
- **Saved clips**, grouped by day (Today / Yesterday / weekday / date), newest
  first, with a preview image, time, size and age
- **Load older clips** pulls the next page — 12 at a time by default, so the
  page stays fast once you have hundreds of clips

Enter the `.env` secret once in the key box at the bottom; it stays in that
browser. Each device needs it entered once.

**Preview images** are generated by ffmpeg from a frame ~25 seconds before the
end of each clip — the interesting moment is just before the press, not the
start of the window. They're cached in `thumbs/` and regenerated if you delete
them. Tune with `THUMB_OFFSET_SECONDS` and `PAGE_SIZE` in `docker-compose.yml`.

---

## Duplicate presses

The moment a press is accepted, the endpoint closes for **30 seconds**. Every
request in that window gets `429` with a `retry_after` countdown, and no second
export is started.

The check and the claim happen under one lock, so two requests arriving in the
same millisecond cannot both pass — the loser sees the winner's timestamp. This
is tested with 25 simultaneous requests: exactly one is accepted, twenty-four
are refused, and exactly one clip is produced.

Worth knowing:

- Rejected presses **do not** extend the window. Hammering the button doesn't
  push the unlock further away; `retry_after` counts steadily down.
- A wrong key returns `401` and starts no cooldown, so someone with the wrong
  secret can't lock out the real button.
- The ESP32 keeps its own matching 30-second cooldown, so a held button doesn't
  even reach the network.
- The window lives in the receiver's memory, which is why the Dockerfile pins
  `--workers 1`. Two worker processes would each keep their own timestamp and a
  duplicate could slip through.

Change it in `docker-compose.yml` with `COOLDOWN_SECONDS`, and keep
`COOLDOWN_MS` in the firmware in step. `curl http://localhost:5001/health`
reports the current window and how many duplicates have been blocked.

---

## Everyday commands

| Task | Command |
|---|---|
| Start (foreground) | `docker-compose up frigate receiver fakecam` |
| Start (background) | `docker-compose up -d frigate receiver fakecam` |
| Stop | `docker-compose down` |
| What's running? | `docker-compose ps` |
| Receiver logs | `docker-compose logs -f receiver` |
| Frigate logs | `docker-compose logs -f frigate` |
| Apply a config change | `docker-compose restart frigate` |
| Is the receiver healthy? | `curl http://localhost:5001/health` |
| Recent press history | `curl http://localhost:5001/presses` |
| Rebuild after a UI change | `docker-compose up -d --build receiver` |
| Clear cached previews | `rm -rf thumbs/*` |

---

## Running the automated tests (optional)

These check the receiver's logic without any camera, Frigate, or Docker.

```
python3 -m venv .venv
source .venv/bin/activate
pip install flask requests pytest
cd receiver
pytest -v
```

Expect `10 passed`.

Two things that trip people up: the virtual environment lives in whichever
folder you created it in, so create it in the project folder and not a copy of
it elsewhere. And every new terminal window needs `source .venv/bin/activate`
again before Python will find the packages — "ModuleNotFoundError" almost
always means you skipped that line.

Install `flask requests pytest` rather than `requirements.txt`; that file also
lists `gunicorn`, which only runs inside Docker.

---

## Moving to the real hardware

Do these in order. Each step proves the one before it.

**1. Camera alone.** Put the real RTSP URL in `frigate/config.yml`, restore the
real config if you swapped it (`cp frigate/config.real.yml frigate/config.yml`),
then `docker-compose up -d frigate`. Confirm you see the mat at
<http://localhost:5000> and that files appear under `storage/recordings/`.

**2. Receiver against the real camera.** Run the same curl command. Wait, then
check Export. You should get a real clip of the mat.

**3. Button on the bench, no mat.** Open `firmware/button_trigger.ino`, set
`PRINT_RAW_STATE = true`, flash the ESP32, open the Serial Monitor. Press the
button and watch the readings: it should show **LOW at rest** and **HIGH when
pressed**. If it's the other way around, change `PRESSED_STATE` to `LOW`. Then
set `PRINT_RAW_STATE` back to `false`.

**4. Fill in the sketch and flash it:**

```c
const char* WIFI_SSID     = "your gym wifi";
const char* WIFI_PASSWORD = "your wifi password";
const char* RECEIVER_HOST = "192.168.1.50";   // this computer's IP
const char* SHARED_SECRET = "the value from .env";   // must match exactly
```

Find your computer's IP on Mac with `ipconfig getifaddr en0`. Set a DHCP
reservation on the router so it doesn't change.

**5. Press the button for real.** Watch the onboard LED:

| LED | Meaning |
|---|---|
| One long blink | Clip saved |
| Two short blinks | Cooldown — pressed again too soon |
| Five fast blinks | Error: wrong secret, receiver down, or Wi-Fi dropped |

---

## Hardware notes

**Check VIN before connecting the battery pack.** Two 18650s in series give
8.4V when fully charged. On a classic WROOM-32 DevKit that feeds a regulator
rated to ~15V and is fine (it runs warm). On some boards VIN is wired straight
to the 5V rail, and 8.4V destroys it. Test continuity between the VIN and 5V
pins with a multimeter first — if they're connected, don't use the battery pack.

**Battery life is the weak point.** With Wi-Fi permanently on, the ESP32 draws
~100 mA, so 3000 mAh cells last roughly a day and a half. Nobody will swap
batteries that often. Two options:

- *For now:* skip the batteries, run the ESP32 from a USB phone charger. Boring,
  reliable, no code changes.
- *Later:* deep sleep, waking on the button press via `esp_sleep_enable_ext0_wakeup`
  on GPIO4. Power drops to almost nothing and the cells last months. It costs
  2–3 seconds to wake and reconnect Wi-Fi before the request goes out — which
  genuinely doesn't matter here, because the clip is retroactive. Three seconds
  late still captures the same ten minutes.

**Weatherproofing.** The mushroom button is IP66; the ESP32 and battery holder
aren't. Budget for an enclosure if it lives at mat level.

---

## Security

Port **5000** is Frigate's *unauthenticated* internal API — that's what keeps
the receiver simple, and it's exactly why that port must never be forwarded to
the internet. Frigate's authenticated interface is port **8971**; use that if
you ever want remote access.

The shared secret travels in plaintext over HTTP. It prevents accidental
triggers, not a determined attacker already on your Wi-Fi. That's a reasonable
trade for a gym LAN.

---

## Troubleshooting

**"unknown flag: --profile"** — an older or differently-built Compose. Name the
services instead: `docker-compose up frigate receiver fakecam`.

**"docker: unknown command: docker compose"** — you have the hyphenated
`docker-compose` only. Use the hyphen everywhere.

**Empty or very short clip** — Frigate hasn't been recording long enough.
Check `ls storage/recordings/` has content, and confirm `continuous: days: 3`
is still set in `frigate/config.yml`.

**Export succeeds but there's no file** — check disk space. Continuous 1080p
recording is roughly 30–60 GB per camera per day.

**Camera drops off Wi-Fi** — the iM5 SC is 2.4 GHz only. Check the mat isn't at
the edge of coverage; Frigate's logs will show ffmpeg reconnect attempts.

**Everything was working, now it isn't** — `docker-compose down` then
`docker-compose up -d`. If a config change is involved,
`docker-compose logs frigate | tail -30` will name the offending line.

---

## Contributing / running your own copy

`.env` is gitignored because it holds the shared secret. Clone, then:

```
cp .env.example .env      # put your own secret in it
cp frigate/config.sim.yml frigate/config.yml   # or point config.yml at your camera
docker-compose up -d --build frigate receiver fakecam
```

Tests: `cd receiver && pytest -v` (30 tests, no hardware needed).

---

## Where this is going — NO FLAGRA as a product

Today this repo runs **one** gym. The plan is to let any gym or academy sign
up, keep running its own camera + Pi locally, and get a login to a shared
cloud dashboard — modeled loosely on
[replaysports.com.br](https://www.replaysports.com.br), branded black + a
strong yellow (`#FFD400`), heavy display type (Anton), the identity already
built into the dashboard in `receiver/templates/index.html`.

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
| `Device` | a paired Raspberry Pi — establishment, camera name, hashed device key |
| `Clip` | establishment, device, S3 key, timestamps, size, status — replaces today's `os.listdir()` directory scan |

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
/                 public marketing site (no login)      — Phase 5
/features, /about  more marketing pages                  — Phase 5
/signup             "Start your gym" — creates User +
                     Establishment + Membership(admin)    — Phase 1
/login               session login                        — Phase 1
/invite/<token>       accept an invite, set a password     — Phase 1

/app/                the existing black/yellow dashboard,   — Phase 4
                      now scoped to g.establishment:
                        - live view (LAN-only banner if
                          viewed off the gym's network)
                        - clip library, from Postgres +
                          presigned S3 URLs
/app/devices           admin: generate a pairing code,       — Phase 2
                        see each Pi's status
/app/team               admin: invite/manage members          — Phase 1
```

### Build order

Each phase leaves the system working end to end; the existing gym keeps
running throughout.

0. **Scaffolding** — split into `edge/` (today's `receiver/`, `frigate/`,
   `firmware/`, unchanged behavior) and `cloud/` (new Flask + Postgres app).
1. **Cloud identity & tenancy** — schema, login, "Start your gym" signup,
   admin invites. Migrate the real gym through this flow.
2. **Device pairing + clip metadata** — pairing codes, edge app posts clip
   metadata to the cloud after each export; playback still points at the
   Pi's LAN address.
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
- [ ] Real camera streaming into Frigate
- [ ] Real button, end to end
- [ ] Deep sleep for battery life
- [ ] Moved to the Raspberry Pi
- [ ] Cloud app: accounts, tenancy, invites (Phase 1)
- [ ] Device pairing + clip metadata in Postgres (Phase 2)
- [ ] S3 upload pipeline (Phase 3)
- [ ] Post-login dashboard live at `/app` (Phase 4)
- [ ] Public marketing site (Phase 5)
- [ ] Second gym onboarded (Phase 6)
