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
import os
import threading
import time
from collections import deque
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request, send_from_directory


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

app = Flask(__name__)

_lock = threading.Lock()
_last_trigger = 0.0
_recent = deque(maxlen=25)  # newest last
_threads = []  # export threads, kept so tests can join them
_blocked = 0   # duplicate presses rejected since start


def log(msg):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def clip_name(press_ts):
    stamp = datetime.fromtimestamp(press_ts).strftime("%Y-%m-%d_%H-%M-%S")
    return f"mat_{stamp}"


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


def _deferred_export(press_ts, name):
    """Wait out the post-roll, then export. Runs on a background thread."""
    time.sleep(POST_ROLL_SECONDS)
    start_ts = press_ts - LOOKBACK_SECONDS
    end_ts = press_ts + POST_ROLL_SECONDS

    ok, detail = export_range(CAMERA_NAME, start_ts, end_ts, name)
    entry = {
        "name": name,
        "pressed_at": int(press_ts),
        "start": int(start_ts),
        "end": int(end_ts),
        "ok": ok,
        "detail": detail,
    }
    with _lock:
        _recent.append(entry)

    if ok:
        log(f"Export requested: {name} ({LOOKBACK_SECONDS}s lookback) -> {detail}")
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

    # Check and claim under one lock. Two requests arriving in the same
    # millisecond cannot both pass: the loser sees the winner's timestamp.
    with _lock:
        since = now - _last_trigger
        if since < COOLDOWN_SECONDS:
            _blocked += 1
            remaining = round(COOLDOWN_SECONDS - since, 1)
            log(f"Duplicate press blocked ({since:.1f}s into {COOLDOWN_SECONDS}s cooldown)")
            return jsonify({
                "status": "cooldown",
                "retry_after": remaining,
                "cooldown_seconds": COOLDOWN_SECONDS,
            }), 429
        _last_trigger = now   # claimed - every other request now bounces

    name = clip_name(now)
    log(f"Button press accepted -> {name}, exporting in {POST_ROLL_SECONDS}s")
    thread = threading.Thread(target=_deferred_export, args=(now, name), daemon=True)
    _threads.append(thread)
    thread.start()

    # Reply immediately so the ESP32 isn't holding a socket open for 15s.
    return jsonify({"status": "accepted", "clip": name, "lookback_seconds": LOOKBACK_SECONDS}), 202


@app.route("/", methods=["GET"])
def dashboard():
    return render_template(
        "index.html",
        camera=CAMERA_NAME.replace("_", " "),
        minutes=round(LOOKBACK_SECONDS / 60),
        lookback=LOOKBACK_SECONDS,
        cooldown=COOLDOWN_SECONDS,
        page_size=PAGE_SIZE,
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

    page = []
    for mtime, size, name in everything[offset:offset + limit]:
        when = datetime.fromtimestamp(mtime)
        page.append({
            "file": name,
            "day": _day_label(when, today),
            "date": when.strftime("%Y-%m-%d"),
            "time": when.strftime("%H:%M"),
            "ago": _humanise_age(now - mtime),
            "size_mb": round(size / 1048576, 1),
            "thumb": f"/thumbs/{name}.jpg",
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


@app.route("/presses", methods=["GET"])
def presses():
    """Recent export attempts, newest first. Handy while testing."""
    with _lock:
        return jsonify(list(reversed(_recent))), 200


@app.route("/health", methods=["GET"])
def health():
    with _lock:
        since = time.time() - _last_trigger if _last_trigger else None
    body = {
        "status": "alive",
        "camera": CAMERA_NAME,
        "frigate": FRIGATE_URL,
        "dry_run": DRY_RUN,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "cooldown_active": since is not None and since < COOLDOWN_SECONDS,
        "duplicates_blocked": _blocked,
    }
    try:
        resp = requests.get(f"{FRIGATE_URL}/api/version", timeout=3)
        body["frigate_reachable"] = resp.ok
        body["frigate_version"] = resp.text.strip()
    except requests.RequestException as exc:
        body["frigate_reachable"] = False
        body["frigate_error"] = str(exc)
    return jsonify(body), 200


if __name__ == "__main__":
    # NOTE: the cooldown lives in this process's memory. Run exactly one
    # worker (the Dockerfile pins --workers 1); with two, each would keep its
    # own timestamp and a duplicate could slip through.
    if SHARED_SECRET == "change-me-to-something-random":
        log("WARNING: RECEIVER_SECRET is still the default value")
    log(f"Receiver up on :{PORT}, camera={CAMERA_NAME}, lookback={LOOKBACK_SECONDS}s, frigate={FRIGATE_URL}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
