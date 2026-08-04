"""
Uploads saved clips to the cloud, which puts them in R2.

Shape of the thing:

    manage page -> queue (on disk) -> one worker thread -> cloud handshake

Deliberate choices, and why:

*Only what someone chose.* The continuous recording never leaves the Pi. A
gym generates ~43 GB a day of buffer and maybe 3 GB of saved clips; uploading
the tape would cost more than the subscription and take longer than a day.

*One at a time.* A gym's upstream is shared with card machines, music and
whoever is on a video call in the office. Two 300 MB uploads racing each other
is how you get a coach complaining the Wi-Fi is broken.

*The queue is a file, not memory.* Power cuts happen. A clip queued before a
reboot must still upload after it.

*Retries back off and give up loudly.* A clip that can't upload becomes a
visible "failed" with a reason, not a silent gap.

*No R2 credentials here.* The Pi asks the cloud for a presigned URL and PUTs
to it. A stolen Pi yields a device key that can register clips and request
upload slots — it cannot read the bucket.
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timezone

import requests

# mat_camera_20260723_164652-20260723_165707_7o4jf6.mp4
EXPORT_NAME = re.compile(
    r"^(?P<camera>.+)_(?P<start>\d{8}_\d{6})-(?P<end>\d{8}_\d{6})_(?P<sid>[A-Za-z0-9]+)\.mp4$"
)

# Wait this long after the Nth consecutive failure before trying again.
BACKOFF = [30, 120, 600, 1800, 3600]
MAX_ATTEMPTS = 8


def parse_export_name(filename):
    """(camera, start_dt, end_dt) from a Frigate export filename, or None.

    Lets a clip be registered with the cloud from the file alone, which is how
    a Pi recovers clips that were exported while the cloud was unreachable.
    """
    match = EXPORT_NAME.match(filename or "")
    if not match:
        return None
    try:
        start = datetime.strptime(match["start"], "%Y%m%d_%H%M%S")
        end = datetime.strptime(match["end"], "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return match["camera"], start, end


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Uploader:
    """Owns the queue file, the worker thread and the cloud conversation."""

    def __init__(self, config, log=print):
        # Either a plain dict or a callable returning one. The callable form
        # matters because pairing can happen after this object exists: the
        # worker must see the device key the moment it's written, not the
        # empty string that was there at import.
        self._config = config
        self.log = log
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._thread = None
        self._stop = False
        self._state = {}     # local_filename -> record
        self._current = None  # what's uploading right now, for the UI
        self._load()

    @property
    def config(self):
        return self._config() if callable(self._config) else self._config

    # ---- persistence ----

    @property
    def _path(self):
        return os.path.join(self.config["data_dir"], "uploads.json")

    def _load(self):
        try:
            with open(self._path) as fh:
                stored = json.load(fh)
        except (OSError, ValueError):
            stored = {}
        if isinstance(stored, dict):
            # Anything caught mid-flight when the power went out is retried,
            # not abandoned: the cloud is the authority on whether it landed.
            for record in stored.values():
                if isinstance(record, dict) and record.get("status") == "uploading":
                    record["status"] = "queued"
            self._state = stored

    def _save(self):
        os.makedirs(self.config["data_dir"], exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(self._state, fh, indent=2)
        os.replace(tmp, self._path)

    # ---- public surface ----

    def state_for(self, filename):
        with self._lock:
            record = self._state.get(filename)
            return dict(record) if record else None

    def all_state(self):
        with self._lock:
            return {name: dict(record) for name, record in self._state.items()}

    def current(self):
        with self._lock:
            return dict(self._current) if self._current else None

    def enqueue(self, filename):
        """Queue a clip, or return its existing record if already handled."""
        with self._lock:
            record = self._state.get(filename)
            if record and record.get("status") == "ready":
                return dict(record)
            record = record or {}
            record.update({
                "file": filename,
                "status": "queued",
                "error": None,
                "queued_at": time.time(),
                "not_before": 0,
            })
            record.setdefault("attempts", 0)
            self._state[filename] = record
            self._save()
        self._wake.set()
        return dict(record)

    def forget(self, filename):
        """Drop a clip from the queue — used when the file is deleted."""
        with self._lock:
            removed = self._state.pop(filename, None)
            if removed:
                self._save()
        return removed is not None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        self._wake.set()

    # ---- the worker ----

    def _next_due(self):
        now = time.time()
        with self._lock:
            due = [
                record for record in self._state.values()
                if record.get("status") in ("queued", "retry")
                and record.get("not_before", 0) <= now
            ]
        due.sort(key=lambda r: r.get("queued_at", 0))
        return due[0]["file"] if due else None

    def _run(self):
        while not self._stop:
            filename = self._next_due()
            if filename is None:
                self._wake.wait(timeout=30)
                self._wake.clear()
                continue
            try:
                self._upload_one(filename)
            except Exception as exc:  # a worker thread must never die
                self.log(f"Uploader crashed on {filename}: {exc}")
                self._fail(filename, str(exc))

    def _set(self, filename, **fields):
        with self._lock:
            record = self._state.setdefault(filename, {"file": filename, "attempts": 0})
            record.update(fields)
            self._save()
            return dict(record)

    def _fail(self, filename, message, permanent=False):
        with self._lock:
            record = self._state.setdefault(filename, {"file": filename, "attempts": 0})
            record["attempts"] = record.get("attempts", 0) + 1
            record["error"] = str(message)[:300]
            attempts = record["attempts"]
            if permanent or attempts >= MAX_ATTEMPTS:
                record["status"] = "failed"
                record["not_before"] = 0
            else:
                delay = BACKOFF[min(attempts - 1, len(BACKOFF) - 1)]
                record["status"] = "retry"
                record["not_before"] = time.time() + delay
            self._save()
            status, attempts = record["status"], record["attempts"]
        self.log(f"Upload {status} for {filename} (attempt {attempts}): {message}")

    # ---- the cloud conversation ----

    def _headers(self):
        return {
            "Authorization": f"Device {self.config['device_uuid']}:{self.config['device_key']}"
        }

    def _cloud(self, path):
        return f"{self.config['cloud_url'].rstrip('/')}{path}"

    def _register(self, filename, size_bytes):
        """Get (or create) the cloud's row for this clip. Idempotent server-side."""
        parsed = parse_export_name(filename)
        if not parsed:
            raise ValueError(f"cannot read a time window out of '{filename}'")
        camera, start, end = parsed
        payload = {
            "camera_name": self.config["camera_name"],
            "pressed_at": _iso(end),
            "start_ts": _iso(start),
            "end_ts": _iso(end),
            "duration_seconds": int((end - start).total_seconds()),
            "size_bytes": size_bytes,
            "local_filename": filename,
        }
        resp = requests.post(
            self._cloud("/api/clips"), json=payload,
            headers=self._headers(), timeout=self.config["timeout"],
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"register failed: HTTP {resp.status_code} {resp.text[:200]}")
        return resp.json()["clip_id"]

    def _upload_one(self, filename):
        source = os.path.join(self.config["exports_dir"], filename)
        if not os.path.exists(source):
            self.log(f"Upload skipped, file is gone: {filename}")
            self.forget(filename)
            return

        if not self.config.get("paired"):
            self._fail(filename, "this Pi is not paired with a cloud account", permanent=True)
            return

        size = os.path.getsize(source)
        self._set(filename, status="uploading", error=None)
        with self._lock:
            self._current = {"file": filename, "bytes": size, "sent": 0, "started": time.time()}

        try:
            record = self.state_for(filename) or {}
            clip_id = record.get("clip_id") or self._register(filename, size)
            self._set(filename, clip_id=clip_id)

            slot = requests.post(
                self._cloud(f"/api/clips/{clip_id}/upload-url"),
                json={"local_filename": filename},
                headers=self._headers(), timeout=self.config["timeout"],
            )
            if slot.status_code != 200:
                raise RuntimeError(f"no upload slot: HTTP {slot.status_code} {slot.text[:200]}")
            slot = slot.json()

            self.log(f"Uploading {filename} ({round(size / 1048576)} MB)")
            with open(source, "rb") as fh:
                tracked = _Progress(fh, size, self._progress)
                put = requests.put(
                    slot["url"], data=tracked,
                    headers={
                        "Content-Type": slot.get("content_type", "video/mp4"),
                        "Content-Length": str(size),
                    },
                    timeout=self.config["upload_timeout"],
                )
            if put.status_code not in (200, 201, 204):
                raise RuntimeError(f"PUT rejected: HTTP {put.status_code} {put.text[:200]}")

            done = requests.post(
                self._cloud(f"/api/clips/{clip_id}/uploaded"),
                json={"size_bytes": size},
                headers=self._headers(), timeout=self.config["timeout"],
            )
            if done.status_code != 200:
                raise RuntimeError(f"confirm failed: HTTP {done.status_code} {done.text[:200]}")
            body = done.json()

            self._set(
                filename, status="ready", error=None,
                share_url=body.get("share_url"), uploaded_at=time.time(),
                size_bytes=size,
            )
            self.log(f"Uploaded {filename} -> {body.get('share_url')}")

        except requests.RequestException as exc:
            self._fail(filename, f"network: {exc}")
        except (RuntimeError, ValueError, OSError) as exc:
            self._fail(filename, str(exc))
        finally:
            with self._lock:
                self._current = None

    def _progress(self, sent, total):
        with self._lock:
            if self._current:
                self._current["sent"] = sent


class _Progress:
    """File wrapper that reports how much has been read.

    requests streams a file object straight to the socket, so reading is
    sending — close enough for a progress bar, and it keeps a 300 MB clip out
    of memory.
    """

    def __init__(self, fh, total, callback):
        self._fh = fh
        self._total = total
        self._callback = callback
        self._sent = 0

    def __len__(self):
        return self._total

    def read(self, size=-1):
        chunk = self._fh.read(size)
        if chunk:
            self._sent += len(chunk)
            self._callback(self._sent, self._total)
        return chunk
