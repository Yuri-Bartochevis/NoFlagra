"""
Gym Instant Replay - receiver

Small HTTP server the ESP32 button box talks to. On a valid request it asks
Frigate to EXPORT the last N minutes of continuous recording for the mat
camera into /media/frigate/exports.

Why export and not a "manual event":
    Frigate's record.*.pre_capture only reaches back into the recording cache,
    which holds seconds - not the 10 minutes this project needs. Continuous
    recording + the export API gives an arbitrary lookback window.

Config is all environment variables (see .env.example). Run:
    pip install -r requirements.txt
    python app.py
"""

import hmac
import json
import os
import shutil
import threading
import time
from collections import deque
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template, request, send_from_directory

from uploader import Uploader


def _env_int(name, default):
    return int(os.environ.get(name, default))


SHARED_SECRET = os.environ.get("RECEIVER_SECRET", "change-me-to-something-random")
FRIGATE_URL = os.environ.get("FRIGATE_URL", "http://localhost:5000").rstrip("/")
CAMERA_NAME = os.environ.get("CAMERA_NAME", "mat_camera")

# How far back the saved clip reaches from the moment of the button press.
LOOKBACK_SECONDS = _env_int("LOOKBACK_SECONDS", 600)
# Keep recording a little past the press, and wait that long before exporting
# so the trailing segments have been flushed from cache to disk.
POST_ROLL_SECONDS = _env_int("POST_ROLL_SECONDS", 15)
# Ignore repeat presses inside this window (button bounce, someone leaning on
# it, two people pressing at once, the ESP32 retrying after a flaky reply).
# The window opens the instant a press is accepted, before any work is done.
COOLDOWN_SECONDS = _env_int("COOLDOWN_SECONDS", 30)
FRIGATE_TIMEOUT = _env_int("FRIGATE_TIMEOUT", 10)
PORT = _env_int("PORT", 5001)
# DRY_RUN=1 logs what it would export without calling Frigate.
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
# Where Frigate writes finished clips, as seen from inside this container.
EXPORTS_DIR = os.environ.get("EXPORTS_DIR", "/media/frigate/exports")
# Writable cache for generated preview images (exports itself is mounted read-only).
THUMBS_DIR = os.environ.get("THUMBS_DIR", "/thumbs")
# Preview frame is taken this many seconds before the end of the clip - the
# interesting moment is right before the press, not the start of the window.
THUMB_OFFSET_SECONDS = _env_int("THUMB_OFFSET_SECONDS", 25)
PAGE_SIZE = _env_int("PAGE_SIZE", 12)

# --- cloud link (Phase 2) --------------------------------------------------
# Written by tools/pair_device.py. All three unset means this Pi hasn't been
# paired, and the receiver runs exactly as it did before the cloud existed —
# the gym running today must keep working untouched.
CLOUD_URL = os.environ.get("CLOUD_URL", "").rstrip("/")
DEVICE_UUID = os.environ.get("DEVICE_UUID", "")
DEVICE_KEY = os.environ.get("DEVICE_KEY", "")
CLOUD_TIMEOUT = _env_int("CLOUD_TIMEOUT", 10)

# --- manage UI (Phase 2.5) -------------------------------------------------
# Where Frigate writes the continuous recording segments, as seen from here.
# Read-only to us — we only measure it, Frigate owns its retention.
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/media/frigate/recordings")
# Writable scratch for settings the manage page edits and the keep-list.
DATA_DIR = os.environ.get("DATA_DIR", "/data")
# Password for anything destructive. Falls back to the button key so an
# existing install keeps working without touching its .env — but set it, so
# the secret baked into the ESP32 firmware isn't also the delete key.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "") or SHARED_SECRET
# What Frigate's config.yml says (record.continuous.days). We can't change it
# from here, we just show it next to the measured numbers.
FRIGATE_RETENTION_DAYS = _env_int("FRIGATE_RETENTION_DAYS", 3)

app = Flask(__name__)

_lock = threading.Lock()
_last_trigger = 0.0
_recent = deque(maxlen=25)  # newest last
_threads = []  # export threads, kept so tests can join them
_blocked = 0   # duplicate presses rejected since start


def log(msg):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


# --- runtime settings ------------------------------------------------------
# The clip window used to be env-only, which meant a container restart to
# change it. The manage page edits these live instead: env vars are now the
# defaults, and settings.json (if present) wins. A press snapshots the values
# it needs, so editing mid-export can't produce a half-old, half-new clip.

# name -> (default, minimum, maximum)
SETTING_SPEC = {
    "lookback_seconds": (LOOKBACK_SECONDS, 30, 3600),
    "post_roll_seconds": (POST_ROLL_SECONDS, 0, 300),
    "cooldown_seconds": (COOLDOWN_SECONDS, 0, 3600),
}

_settings_lock = threading.Lock()
_settings = {name: spec[0] for name, spec in SETTING_SPEC.items()}


def _state_path(filename):
    return os.path.join(DATA_DIR, filename)


def _read_json(filename, fallback):
    try:
        with open(_state_path(filename)) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return fallback


def _write_json(filename, payload):
    """Write via a temp file + rename so a crash can't leave a half-written
    settings file that bricks the next start."""
    os.makedirs(DATA_DIR, exist_ok=True)
    target = _state_path(filename)
    tmp = target + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, target)


def load_settings():
    """Merge settings.json over the env defaults. Bad values are ignored
    rather than fatal — a typo in the file must not stop the gym recording."""
    stored = _read_json("settings.json", {})
    with _settings_lock:
        for name, (default, low, high) in SETTING_SPEC.items():
            value = stored.get(name, default)
            try:
                value = int(value)
            except (TypeError, ValueError):
                log(f"settings.json: {name}={value!r} is not a number, using {default}")
                value = default
            if not low <= value <= high:
                log(f"settings.json: {name}={value} out of range, using {default}")
                value = default
            _settings[name] = value
        return dict(_settings)


def settings():
    with _settings_lock:
        return dict(_settings)


def save_settings(incoming):
    """Validate and persist. Returns (ok, result) where result is the new
    settings on success or an error string on failure."""
    cleaned = {}
    for name, value in incoming.items():
        if name not in SETTING_SPEC:
            return False, f"unknown setting: {name}"
        default, low, high = SETTING_SPEC[name]
        try:
            number = int(value)
        except (TypeError, ValueError):
            return False, f"{name} must be a whole number of seconds"
        if not low <= number <= high:
            return False, f"{name} must be between {low} and {high} seconds"
        cleaned[name] = number

    with _settings_lock:
        _settings.update(cleaned)
        snapshot = dict(_settings)
    try:
        _write_json("settings.json", snapshot)
    except OSError as exc:
        return False, f"could not write settings: {exc}"
    log(f"Settings changed: {cleaned}")
    return True, snapshot


def kept_clips():
    stored = _read_json("keep.json", [])
    return set(stored) if isinstance(stored, list) else set()


def set_kept(filename, keep):
    current = kept_clips()
    current.add(filename) if keep else current.discard(filename)
    _write_json("keep.json", sorted(current))
    return current


def require_admin():
    """Returns an error response if the request isn't authorised, else None."""
    token = request.headers.get("X-Admin-Token", "")
    if not hmac.compare_digest(token, ADMIN_PASSWORD):
        log(f"Rejected admin request from {request.remote_addr}: bad password")
        return jsonify({"error": "unauthorized"}), 401
    return None


# --- uploads (Phase 3) -----------------------------------------------------
# Sharing is opt-in per clip. Nothing leaves the building until someone at the
# gym picks a clip and says so — which is the whole storage-cost argument and
# also the honest answer when a member asks where their footage goes.

# How long a single PUT may take. A 300 MB original on a slow gym uplink can
# genuinely run for twenty minutes; timing out at 60s would mean it never
# completes, on any night when the gym is busy.
UPLOAD_TIMEOUT = _env_int("UPLOAD_TIMEOUT", 1800)

def _upload_config():
    """Read live, not snapshotted: pairing writes these after import."""
    return {
        "data_dir": DATA_DIR,
        "exports_dir": EXPORTS_DIR,
        "camera_name": CAMERA_NAME,
        "cloud_url": CLOUD_URL,
        "device_uuid": DEVICE_UUID,
        "device_key": DEVICE_KEY,
        "paired": cloud_paired(),
        "timeout": CLOUD_TIMEOUT,
        "upload_timeout": UPLOAD_TIMEOUT,
    }


# Constructed at the bottom of the module, once cloud_paired() exists.
uploads = None


def clip_name(press_ts):
    stamp = datetime.fromtimestamp(press_ts).strftime("%Y-%m-%d_%H-%M-%S")
    return f"mat_{stamp}"


def frigate_export_filename(camera, start_ts, end_ts, export_id):
    """The file Frigate will actually write for an export.

    Frigate does NOT name the file after the `name` we pass — that only
    becomes a display name in its database. The path is built in
    frigate/record/export.py as:

        {camera}_{start:%Y%m%d_%H%M%S}-{end:%Y%m%d_%H%M%S}_{suffix}.mp4

    where suffix is the trailing chunk of the export_id the API hands back.
    Deterministic, so we can name the file before it exists — which matters
    because the export runs asynchronously and the POST returns immediately.
    """
    if not export_id:
        return None
    suffix = export_id.split("_")[-1]
    start = datetime.fromtimestamp(int(start_ts)).strftime("%Y%m%d_%H%M%S")
    end = datetime.fromtimestamp(int(end_ts)).strftime("%Y%m%d_%H%M%S")
    return f"{camera}_{start}-{end}_{suffix}.mp4"


def export_range(camera, start_ts, end_ts, name):
    """Ask Frigate to export a time range. Returns (ok, detail)."""
    url = f"{FRIGATE_URL}/api/export/{camera}/start/{int(start_ts)}/end/{int(end_ts)}"
    payload = {"playback": "realtime", "source": "recordings", "name": name}

    if DRY_RUN:
        log(f"DRY_RUN: would POST {url} {payload}")
        return True, {"dry_run": True}

    try:
        resp = requests.post(url, json=payload, timeout=FRIGATE_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return False, str(exc)

    try:
        return True, resp.json()
    except ValueError:
        return True, resp.text


def cloud_paired():
    return bool(CLOUD_URL and DEVICE_UUID and DEVICE_KEY)


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def post_clip_metadata(press_ts, start_ts, end_ts, name, local_filename=None):
    """Tell the cloud a clip exists. Best effort — never raises.

    Deliberately fire-and-forget: the clip is already safe on local disk, and
    the whole point of the edge/cloud split is that a cloud outage must not
    affect recording. A failure here just means the row shows up later, once
    Phase 3's retry queue reconciles what's on disk against what's in the
    cloud.

    size_bytes is 0 because Frigate exports asynchronously — the file does
    not exist yet when the export API returns. Phase 3 fills in the real
    size at upload time, which is also when status leaves "pending".

    local_filename is what Frigate will call the file on disk, which is NOT
    derived from `name` (see frigate_export_filename). Getting this wrong
    means Phase 3's uploader looks for a file that never existed.
    """
    if not cloud_paired():
        return None

    payload = {
        "camera_name": CAMERA_NAME,
        "pressed_at": _iso(press_ts),
        "start_ts": _iso(start_ts),
        "end_ts": _iso(end_ts),
        "duration_seconds": int(end_ts - start_ts),
        "size_bytes": 0,
        "local_filename": local_filename or f"{name}.mp4",
    }
    try:
        resp = requests.post(
            f"{CLOUD_URL}/api/clips",
            json=payload,
            headers={"Authorization": f"Device {DEVICE_UUID}:{DEVICE_KEY}"},
            timeout=CLOUD_TIMEOUT,
        )
    except requests.RequestException as exc:
        log(f"Cloud unreachable, clip {name} not registered: {exc}")
        return None

    if resp.status_code == 201:
        log(f"Clip {name} registered with the cloud")
        return resp
    log(f"Cloud rejected clip {name}: HTTP {resp.status_code} {resp.text.strip()[:200]}")
    return resp


def _deferred_export(press_ts, name, lookback, post_roll):
    """Wait out the post-roll, then export. Runs on a background thread.

    lookback and post_roll are snapshotted at press time by the caller, so a
    settings change while this thread sleeps can't produce a clip whose
    window doesn't match what the presser was told they'd get.
    """
    time.sleep(post_roll)
    start_ts = press_ts - lookback
    end_ts = press_ts + post_roll

    ok, detail = export_range(CAMERA_NAME, start_ts, end_ts, name)

    export_id = detail.get("export_id") if isinstance(detail, dict) else None
    local_filename = frigate_export_filename(CAMERA_NAME, start_ts, end_ts, export_id)

    entry = {
        "name": name,
        "pressed_at": int(press_ts),
        "start": int(start_ts),
        "end": int(end_ts),
        "ok": ok,
        "detail": detail,
        "file": local_filename,
    }
    with _lock:
        _recent.append(entry)

    if ok:
        log(f"Export requested: {name} ({lookback}s lookback) -> {local_filename or detail}")
        # Only after a successful export: a clip that never got cut has
        # nothing to register.
        post_clip_metadata(press_ts, start_ts, end_ts, name, local_filename)
    else:
        log(f"EXPORT FAILED for {name}: {detail}")


@app.route("/save-clip", methods=["POST"])
def save_clip():
    token = request.headers.get("X-Auth-Token", "")
    if not hmac.compare_digest(token, SHARED_SECRET):
        log(f"Rejected request from {request.remote_addr}: bad token")
        return jsonify({"error": "unauthorized"}), 401

    global _last_trigger, _blocked
    now = time.time()
    current = settings()
    cooldown = current["cooldown_seconds"]
    lookback = current["lookback_seconds"]
    post_roll = current["post_roll_seconds"]

    # Check and claim under one lock. Two requests arriving in the same
    # millisecond cannot both pass: the loser sees the winner's timestamp.
    with _lock:
        since = now - _last_trigger
        if since < cooldown:
            _blocked += 1
            remaining = round(cooldown - since, 1)
            log(f"Duplicate press blocked ({since:.1f}s into {cooldown}s cooldown)")
            return jsonify({
                "status": "cooldown",
                "retry_after": remaining,
                "cooldown_seconds": cooldown,
            }), 429
        _last_trigger = now   # claimed - every other request now bounces

    name = clip_name(now)
    log(f"Button press accepted -> {name}, exporting in {post_roll}s")
    thread = threading.Thread(
        target=_deferred_export, args=(now, name, lookback, post_roll), daemon=True
    )
    _threads.append(thread)
    thread.start()

    # Reply immediately so the ESP32 isn't holding a socket open for 15s.
    return jsonify({"status": "accepted", "clip": name, "lookback_seconds": lookback}), 202


@app.route("/", methods=["GET"])
def dashboard():
    current = settings()
    return render_template(
        "index.html",
        camera=CAMERA_NAME.replace("_", " "),
        minutes=round(current["lookback_seconds"] / 60),
        lookback=current["lookback_seconds"],
        cooldown=current["cooldown_seconds"],
        page_size=PAGE_SIZE,
    )


@app.route("/manage", methods=["GET"])
def manage():
    return render_template(
        "manage.html",
        camera=CAMERA_NAME.replace("_", " "),
        page_size=PAGE_SIZE,
        retention_days=FRIGATE_RETENTION_DAYS,
    )


@app.route("/live.jpg", methods=["GET"])
def live():
    """Proxy the camera's latest frame so the page only needs port 5001."""
    try:
        resp = requests.get(f"{FRIGATE_URL}/api/{CAMERA_NAME}/latest.jpg?h=480", timeout=5)
        resp.raise_for_status()
    except requests.RequestException:
        return "", 503
    return resp.content, 200, {"Content-Type": "image/jpeg", "Cache-Control": "no-store"}


def _humanise_age(seconds):
    if seconds < 90:
        return "just now"
    if seconds < 5400:
        return f"{round(seconds / 60)} min ago"
    if seconds < 172800:
        return f"{round(seconds / 3600)} hours ago"
    return f"{round(seconds / 86400)} days ago"


def _day_label(when, today):
    delta = (today - when.date()).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta < 7:
        return when.strftime("%A")
    return when.strftime("%A %d %B")


def _scan_exports():
    """Every clip on disk, newest first. Cheap: one stat per file."""
    try:
        names = os.listdir(EXPORTS_DIR)
    except OSError:
        return []

    found = []
    for name in names:
        if not name.lower().endswith(".mp4"):
            continue
        try:
            stat = os.stat(os.path.join(EXPORTS_DIR, name))
        except OSError:
            continue
        found.append((stat.st_mtime, stat.st_size, name))
    found.sort(reverse=True)
    return found


@app.route("/api/clips", methods=["GET"])
def api_clips():
    """One page of clips, newest first, each tagged with the day it belongs to."""
    try:
        limit = max(1, min(60, int(request.args.get("limit", PAGE_SIZE))))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return jsonify({"error": "limit and offset must be whole numbers"}), 400

    everything = _scan_exports()
    now = time.time()
    today = datetime.fromtimestamp(now).date()
    keeps = kept_clips()
    upload_state = uploads.all_state()

    page = []
    for mtime, size, name in everything[offset:offset + limit]:
        when = datetime.fromtimestamp(mtime)
        record = upload_state.get(name) or {}
        page.append({
            "file": name,
            "day": _day_label(when, today),
            "date": when.strftime("%Y-%m-%d"),
            "time": when.strftime("%H:%M"),
            "ago": _humanise_age(now - mtime),
            "size_mb": round(size / 1048576, 1),
            "thumb": f"/thumbs/{name}.jpg",
            "kept": name in keeps,
            # None until someone shares it. "ready" means it's in R2 and the
            # link below works for anyone who has it.
            "upload": record.get("status"),
            "share_url": record.get("share_url"),
            "upload_error": record.get("error"),
        })

    return jsonify({
        "clips": page,
        "offset": offset,
        "limit": limit,
        "total": len(everything),
        "total_gb": round(sum(f[1] for f in everything) / 1073741824, 2),
        "has_more": offset + limit < len(everything),
    }), 200


def _ffmpeg_binary():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


_thumb_lock = threading.Lock()


def _make_thumb(source, target):
    """Grab one frame near the end of the clip. Returns True on success."""
    import subprocess

    os.makedirs(os.path.dirname(target), exist_ok=True)
    binary = _ffmpeg_binary()
    # -sseof seeks relative to the end, so no need to probe the duration first.
    attempts = [
        [binary, "-y", "-sseof", f"-{THUMB_OFFSET_SECONDS}", "-i", source,
         "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", target],
        [binary, "-y", "-ss", "1", "-i", source,
         "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", target],
    ]
    for cmd in attempts:
        try:
            subprocess.run(cmd, capture_output=True, timeout=45, check=True)
            if os.path.exists(target) and os.path.getsize(target) > 0:
                return True
        except (subprocess.SubprocessError, OSError):
            continue
    return False


@app.route("/thumbs/<path:filename>.jpg", methods=["GET"])
def thumb(filename):
    """Preview image for a clip, generated once then cached on disk."""
    if "/" in filename or "\\" in filename or filename.startswith("."):
        return "", 404

    source = os.path.join(EXPORTS_DIR, filename)
    target = os.path.join(THUMBS_DIR, filename + ".jpg")

    if not os.path.exists(source):
        return "", 404

    fresh = (
        os.path.exists(target)
        and os.path.getmtime(target) >= os.path.getmtime(source)
        and os.path.getsize(target) > 0
    )
    if not fresh:
        with _thumb_lock:  # one ffmpeg at a time; a Pi will thank us
            if not _make_thumb(source, target):
                return "", 404

    return send_from_directory(THUMBS_DIR, filename + ".jpg",
                               max_age=86400, mimetype="image/jpeg")


@app.route("/clips/<path:filename>", methods=["GET"])
def serve_clip(filename):
    """Play or download a finished clip. send_from_directory refuses to
    escape EXPORTS_DIR, so ../ in the name cannot reach the rest of the disk."""
    return send_from_directory(
        EXPORTS_DIR, filename, as_attachment=request.args.get("dl") == "1"
    )


def _safe_clip_name(filename):
    """A clip name that cannot escape EXPORTS_DIR. Returns None if it could."""
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        return None
    if not filename.lower().endswith(".mp4"):
        return None
    return filename


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    """Readable without the password — the numbers are already on the front
    page, and the manage UI needs them before anyone types anything."""
    current = settings()
    return jsonify({
        "settings": current,
        "limits": {
            name: {"min": low, "max": high, "default": default}
            for name, (default, low, high) in SETTING_SPEC.items()
        },
        # Not editable from here: it lives in Frigate's own config.
        "frigate_retention_days": FRIGATE_RETENTION_DAYS,
    }), 200


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    denied = require_admin()
    if denied:
        return denied

    incoming = request.get_json(silent=True)
    if not isinstance(incoming, dict) or not incoming:
        return jsonify({"error": "send a JSON object of settings to change"}), 400

    ok, result = save_settings(incoming)
    if not ok:
        return jsonify({"error": result}), 400
    return jsonify({"settings": result}), 200


@app.route("/api/clips/<path:filename>", methods=["DELETE"])
def api_clip_delete(filename):
    denied = require_admin()
    if denied:
        return denied

    safe = _safe_clip_name(filename)
    if not safe:
        return jsonify({"error": "bad filename"}), 400

    if safe in kept_clips():
        return jsonify({"error": "clip is marked keep — unmark it first"}), 409

    target = os.path.join(EXPORTS_DIR, safe)
    if not os.path.exists(target):
        return jsonify({"error": "not found"}), 404

    try:
        size = os.path.getsize(target)
        os.remove(target)
    except OSError as exc:
        # Almost always the read-only mount. Say so rather than "500".
        return jsonify({"error": f"could not delete: {exc}"}), 500

    # Best effort — a stale thumb is cosmetic, and it regenerates anyway.
    try:
        os.remove(os.path.join(THUMBS_DIR, safe + ".jpg"))
    except OSError:
        pass

    # Drop it from the queue too, so the worker doesn't keep trying to upload
    # a file that no longer exists. Note this does NOT unpublish an already
    # shared copy — see the share note in the README.
    uploads.forget(safe)

    log(f"Deleted clip {safe} ({round(size / 1048576, 1)} MB)")
    return jsonify({"deleted": safe, "freed_mb": round(size / 1048576, 1)}), 200


@app.route("/api/clips/<path:filename>/keep", methods=["POST"])
def api_clip_keep(filename):
    denied = require_admin()
    if denied:
        return denied

    safe = _safe_clip_name(filename)
    if not safe:
        return jsonify({"error": "bad filename"}), 400
    if not os.path.exists(os.path.join(EXPORTS_DIR, safe)):
        return jsonify({"error": "not found"}), 404

    body = request.get_json(silent=True) or {}
    keep = bool(body.get("keep", True))
    try:
        set_kept(safe, keep)
    except OSError as exc:
        return jsonify({"error": f"could not save keep list: {exc}"}), 500
    return jsonify({"file": safe, "kept": keep}), 200


@app.route("/api/clips/<path:filename>/share", methods=["POST"])
def api_clip_share(filename):
    """Queue a clip for upload. Returns immediately — the worker does the work."""
    denied = require_admin()
    if denied:
        return denied

    safe = _safe_clip_name(filename)
    if not safe:
        return jsonify({"error": "bad filename"}), 400
    if not os.path.exists(os.path.join(EXPORTS_DIR, safe)):
        return jsonify({"error": "not found"}), 404
    if not cloud_paired():
        return jsonify({
            "error": "this Pi is not paired with a cloud account — "
                     "run tools/pair_device.py first"
        }), 409

    record = uploads.enqueue(safe)
    log(f"Queued {safe} for upload")
    return jsonify(record), 202


@app.route("/api/uploads", methods=["GET"])
def api_uploads():
    """Everything the uploader knows, plus what it's doing right now."""
    return jsonify({
        "paired": cloud_paired(),
        "cloud_url": CLOUD_URL or None,
        "current": uploads.current(),
        "clips": uploads.all_state(),
    }), 200


def _dir_bytes(path):
    """Total size and file count under a directory. One stat per file."""
    total = 0
    count = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.stat(os.path.join(root, name)).st_size
                count += 1
            except OSError:
                continue
    return total, count


def _measure_recording_rate():
    """Bytes per day the continuous recording actually consumes.

    Measured, not guessed: Frigate lays segments out as
    recordings/YYYY-MM-DD/HH/camera/MM.SS.mp4, so one full hour directory
    scaled to 24 gives the real rate for this camera at its real bitrate.
    We sample the most recent complete hour rather than walking the whole
    buffer, which on a 3-day retention is ~26k files.

    Returns (bytes_per_day, sampled_hour) or (None, None) if there isn't
    enough footage yet to say.
    """
    try:
        days = sorted(d for d in os.listdir(RECORDINGS_DIR) if not d.startswith("."))
    except OSError:
        return None, None

    now = datetime.now()
    current_hour = now.strftime("%Y-%m-%d/%H")

    for day in reversed(days):
        day_path = os.path.join(RECORDINGS_DIR, day)
        try:
            hours = sorted(h for h in os.listdir(day_path) if not h.startswith("."))
        except OSError:
            continue
        for hour in reversed(hours):
            # Skip the hour in progress: it's partial, so it would read low.
            if f"{day}/{hour}" == current_hour:
                continue
            total, count = _dir_bytes(os.path.join(day_path, hour))
            if count:
                return total * 24, f"{day} {hour}:00"
    return None, None


_rate_cache = {"at": 0.0, "value": (None, None)}


def _recording_rate_cached():
    """The measurement walks a few hundred files; once a minute is plenty."""
    now = time.time()
    if now - _rate_cache["at"] > 60:
        _rate_cache["value"] = _measure_recording_rate()
        _rate_cache["at"] = now
    return _rate_cache["value"]


@app.route("/api/storage", methods=["GET"])
def api_storage():
    """Disk reality plus what it means: at this camera's measured bitrate,
    how many days of continuous footage fit, and how long the saved clips
    can keep growing before the disk is full."""
    try:
        total, used, free = shutil.disk_usage(EXPORTS_DIR)
    except OSError as exc:
        return jsonify({"error": f"cannot read the storage volume: {exc}"}), 503

    recordings_bytes, recordings_files = _dir_bytes(RECORDINGS_DIR)
    clips_bytes, clips_files = _dir_bytes(EXPORTS_DIR)
    per_day, sampled = _recording_rate_cached()

    gb = 1073741824

    body = {
        "disk": {
            "total_gb": round(total / gb, 1),
            "used_gb": round(used / gb, 1),
            "free_gb": round(free / gb, 1),
            "used_percent": round(used / total * 100) if total else 0,
        },
        "recordings": {
            "gb": round(recordings_bytes / gb, 2),
            "files": recordings_files,
            "retention_days": FRIGATE_RETENTION_DAYS,
        },
        "clips": {
            "gb": round(clips_bytes / gb, 2),
            "files": clips_files,
            "kept": len(kept_clips()),
        },
    }

    if per_day:
        # What the buffer costs per day, and therefore how much disk a given
        # retention needs. The free space here is what's left AFTER whatever
        # is already on disk, which is what you actually get to spend.
        body["rate"] = {
            "gb_per_day": round(per_day / gb, 2),
            "mbps": round(per_day * 8 / 86400 / 1_000_000, 2),
            "sampled_hour": sampled,
        }
        # "If I gave the buffer everything free plus what it already holds."
        headroom = free + recordings_bytes
        body["projection"] = {
            "max_retention_days": round(headroom / per_day, 1),
            "options": [
                {
                    "days": days,
                    "gb": round(days * per_day / gb, 1),
                    "fits": days * per_day <= headroom,
                }
                for days in (1, 2, 3, 7, 14, 30)
            ],
        }
    else:
        body["rate"] = None
        body["projection"] = None
        body["note"] = "Not enough recorded footage yet to measure the bitrate."

    return jsonify(body), 200


@app.route("/presses", methods=["GET"])
def presses():
    """Recent export attempts, newest first. Handy while testing."""
    with _lock:
        return jsonify(list(reversed(_recent))), 200


@app.route("/health", methods=["GET"])
def health():
    with _lock:
        since = time.time() - _last_trigger if _last_trigger else None
    current = settings()
    body = {
        "status": "alive",
        "camera": CAMERA_NAME,
        "frigate": FRIGATE_URL,
        "dry_run": DRY_RUN,
        "settings": current,
        "cooldown_seconds": current["cooldown_seconds"],
        "cooldown_active": since is not None and since < current["cooldown_seconds"],
        "duplicates_blocked": _blocked,
        # True when ADMIN_PASSWORD is unset and the button key doubles as the
        # delete key — worth surfacing so it doesn't stay that way forever.
        "admin_shares_button_key": ADMIN_PASSWORD == SHARED_SECRET,
        "cloud_paired": cloud_paired(),
        # The key itself never leaves this process.
        "cloud_url": CLOUD_URL or None,
        "device_uuid": DEVICE_UUID or None,
    }
    try:
        resp = requests.get(f"{FRIGATE_URL}/api/version", timeout=3)
        body["frigate_reachable"] = resp.ok
        body["frigate_version"] = resp.text.strip()
    except requests.RequestException as exc:
        body["frigate_reachable"] = False
        body["frigate_error"] = str(exc)
    return jsonify(body), 200


# At import, not just under __main__ — gunicorn never runs the block below.
load_settings()
uploads = Uploader(_upload_config, log=log)
# Picks up anything left queued by a previous run, including a clip that was
# mid-upload when the power went out.
uploads.start()


if __name__ == "__main__":
    # NOTE: the cooldown lives in this process's memory. Run exactly one
    # worker (the Dockerfile pins --workers 1); with two, each would keep its
    # own timestamp and a duplicate could slip through.
    if SHARED_SECRET == "change-me-to-something-random":
        log("WARNING: RECEIVER_SECRET is still the default value")
    if ADMIN_PASSWORD == SHARED_SECRET:
        log("NOTE: ADMIN_PASSWORD is unset, so the button key also deletes clips")
    current = settings()
    log(f"Receiver up on :{PORT}, camera={CAMERA_NAME}, "
        f"lookback={current['lookback_seconds']}s, frigate={FRIGATE_URL}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
