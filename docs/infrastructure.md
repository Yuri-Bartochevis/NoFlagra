# Infrastructure — accounts, devices, cameras, clips

This is the detailed design for the piece of [Phase 2](../README.md#build-order)
that the root README only sketches: how an `Establishment` (a gym's account)
relates to the physical hardware it owns, and how a clip ends up in S3 with a
key someone can actually find by hand. Read the root README's
["Where this is going"](../README.md#where-this-is-going--no-flagra-as-a-product)
section first for the overall edge/cloud split — this page goes one level
deeper on the device/camera/clip side of it.

## Hierarchy

```
Establishment (account)
      │ 1
      ▼
    Device                one Raspberry Pi, identified by a UUID
      │ 1 : N
      ▼
    Camera                one row per camera the Pi's Frigate instance drives
      │ 1 : N
      ▼
     Clip                 one row per button press on that camera
```

A gym signs up and gets an `Establishment`. That establishment is paired to
**one** `Device` (the Pi running Frigate + the receiver). That device can
drive **multiple** `Camera`s — e.g. a gym with two mats, each with its own
camera and its own button, sharing one Pi. Every clip belongs to exactly one
camera.

### Why one device per account, for now

Every gym today runs a single Pi + Frigate box, so a 1:1 `Establishment` ↔
`Device` relationship matches reality and keeps pairing (below) simple: an
admin never has to pick *which* device a new pairing code is for. It's
enforced with a unique constraint on `devices.establishment_id`, not baked
into the shape of the data — `Device` already carries its own UUID and its
own key independent of the establishment, so supporting several devices per
gym later (a second Pi for a second room) is dropping one constraint, not a
redesign. `Camera` already being 1:N under `Device` is what makes multiple
cameras *on one Pi* free today.

## Data model

Extends the table in the [root README](../README.md#data-model-cloud-side-new)
— `Device` and `Clip` change shape, and `Camera` is new:

| Table | What it holds |
|---|---|
| `Establishment` | the tenant — one per gym (unchanged) |
| `Device` | **`uuid`** (public identifier, used in pairing and in API auth — never the numeric PK), `establishment_id` (unique — one device per account), `name` (e.g. "Front desk Pi"), `device_key_hash`, `pairing_status`, `last_seen_at` |
| `Camera` | `device_id`, `name` (matches the name Frigate uses internally, e.g. `mat_camera`), `slug` (used in the S3 path), `created_at` |
| `Clip` | `camera_id` (was `device_id` — a clip belongs to the camera that recorded it), `establishment_id` (kept, denormalized — every tenant-scoped query filters on it directly instead of joining through `Camera` → `Device`), `s3_key` (nullable until Phase 3 uploads it), `pressed_at`, `start_ts`, `end_ts`, `duration_seconds`, `size_bytes`, `status` |

The device's numeric `id` stays as the primary key (foreign keys, indexes),
but nothing external — pairing responses, API auth, S3 paths — ever sees it.
Only the UUID is exposed, so device identifiers stay meaningless to guess and
safe to put in a URL or a QR code later.

## Pairing — scripts, no dashboard UI yet

Phase 2 does pairing as two small CLI scripts talking to two API endpoints,
not an `/app/devices` page. A UI can replace the admin-side script later
without changing the API.

```
   admin, at a laptop                cloud API                Pi, at the gym
──────────────────────      ──────────────────────      ──────────────────────
cloud/scripts/
  create_pairing_code.py
  <establishment-slug>
  <camera names...>
        │
        ├─ refuses if the establishment
        │  already has a Device
        │
        ├─ creates a pending Device
        │  (fresh UUID, no key yet)
        │  + a short pairing code,
        │  hashed, expires ~15 min
        │
        └─ prints the code ──────────────────────────────────▶ (told to the
                                                                  gym over the
                                                                  phone/Slack)
                                                                       │
                                                                       ▼
                                                          edge/tools/pair_device.py
                                                          <cloud-url> <code>
                                                                       │
                                              POST /api/devices/pair   │
                                              { code, camera_names }   │
                                     ◀─────────────────────────────────
        validates code + expiry,
        marks Device paired,
        creates one Camera row
        per name in the request,
        generates the device key
        (shown exactly once)
                                     { device_uuid, device_key,
                                       cameras: [{id, name, slug}, ...] }
                                     ─────────────────────────────────▶
                                                                       │
                                                          writes DEVICE_UUID +
                                                          DEVICE_KEY to
                                                          edge/.env
```

From then on, every export the receiver makes posts clip metadata to
`POST /api/clips`, authenticated with `DEVICE_UUID` + `DEVICE_KEY` and tagged
with which camera produced it — see the API surface below.

Re-running `create_pairing_code.py` for an establishment that already has a
paired `Device` is a hard refusal (one device per account, see above); a
*pending, unpaired* device's code can be regenerated. Multi-camera gyms pass
all their camera names to `create_pairing_code.py` up front, since Phase 2
has no separate "add a camera to an already-paired device" flow yet — that's
a natural, additive follow-up once Phase 2 ships.

## API surface (Phase 2 scope)

Both endpoints are device-facing, not session-authenticated — a Pi has no
user login.

**`POST /api/devices/pair`** — one-time, using the short-lived pairing code.

```json
// request
{ "code": "7K2P9QRM", "camera_names": ["mat_camera", "cage_camera"] }

// response 200
{
  "device_uuid": "b3e1f7b0-...",
  "device_key": "shown-once-store-it-now",
  "cameras": [
    { "id": 1, "name": "mat_camera", "slug": "mat-camera" },
    { "id": 2, "name": "cage_camera", "slug": "cage-camera" }
  ]
}
```

**`POST /api/clips`** — every export, going forward. Auth via
`Authorization: Device <device_uuid>:<device_key>`.

```json
// request
{
  "camera_name": "mat_camera",
  "pressed_at": "2026-08-02T15:30:45Z",
  "start_ts": "2026-08-02T15:20:45Z",
  "end_ts": "2026-08-02T15:31:00Z",
  "duration_seconds": 615,
  "size_bytes": 184320000,
  "local_filename": "mat_2026-08-02_15-30-45.mp4"
}

// response 201
{ "clip_id": 42, "status": "pending" }
```

`local_filename` is what the Pi already calls the export on its own disk
(see `clip_name()` in `edge/receiver/app.py`) — it's carried along so the
Phase 3 upload step knows which local file to push to S3, and so playback
can fall back to the Pi's own `/clips/<filename>` route before that clip has
an `s3_key`. The endpoint bumps `Device.last_seen_at` on every call, which is
what makes "see each Pi's status" possible later without a heartbeat route.

## S3 layout (Phase 3, key format settled now)

The clip metadata Phase 2 captures needs to already imply where Phase 3 will
put the file, so the key format is fixed here rather than improvised later:

```
s3://noflagra-clips/
  {establishment_slug}/
    {camera_slug}/
      2026/08/02/
        20260802-153045-mat-camera.mp4
        20260802-153045-mat-camera.thumb.jpg
```

- **`establishment_slug`, not the numeric id, as the top-level prefix** —
  it's what a human opening the bucket console actually recognizes. The
  slug is already the tenant's stable, unique, URL-safe identifier
  everywhere else in the app (see `make_slug()` in `cloud/app/models.py`);
  reusing it avoids inventing a second identifier. There's no rename feature
  today, so a slug can't drift out from under existing S3 keys — if that
  changes later, this is the thing that breaks first.
- **`camera_slug` under it** — keeps a two-mat gym's clips visually
  separated without another join to figure out which camera a file belongs
  to.
- **`YYYY/MM/DD/` date partitioning** — keeps any one "directory" from
  growing unbounded, and lines up with whatever lifecycle/retention policy
  Phase 6 ends up using (day-granularity expiry).
- **Filename is the sortable timestamp first** (`YYYYMMDD-HHMMSS`), camera
  slug second, so files sort chronologically inside their own folder even
  though the folder already scopes them to one camera.

The Clip row's `s3_key` is the actual source of truth once Phase 3 writes
it — the app never re-derives a path from convention, so this layout is a
readability/ops convention, not something code depends on staying exact.

## Open questions (deliberately unresolved)

- Pairing code regeneration/expiry UX for a device stuck mid-pairing.
- Whether "add a camera to an already-paired device" needs its own pairing
  step or just an authenticated `POST /api/devices/<uuid>/cameras`.
- Multi-device-per-account (see above) — schema supports it, nothing wires
  it up.
- S3 retention/lifecycle policy — flagged in the root README as Phase 6.
