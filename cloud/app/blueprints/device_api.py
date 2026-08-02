"""
The device-facing API — what a gym's Raspberry Pi talks to.

No session auth here: a Pi has no user login. Pairing is a one-time exchange
of a short-lived code for a long-lived device key; everything after that is
authenticated with that key. See docs/infrastructure.md for the flow.
"""

import hmac
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, g, jsonify, request

from ..extensions import db
from ..models import (
    Camera,
    Clip,
    Device,
    generate_device_key,
    hash_device_key,
    hash_pairing_code,
    make_camera_slug,
)

device_api_bp = Blueprint("device_api", __name__, url_prefix="/api")

MAX_CAMERAS_PER_DEVICE = 8


def _now():
    return datetime.now(timezone.utc)


def _error(message, status):
    return jsonify({"error": message}), status


def _parse_ts(value):
    """Accept ISO 8601, tolerating the 'Z' suffix Python < 3.11 rejected.

    Returns an aware UTC datetime, or None if it can't be parsed.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # A naive timestamp from the Pi is UTC by convention; say so explicitly
    # rather than letting it compare as naive later.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def device_auth(view):
    """Authenticate `Authorization: Device <uuid>:<key>`."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, credentials = header.partition(" ")
        if scheme != "Device" or ":" not in credentials:
            return _error("expected 'Authorization: Device <uuid>:<key>'", 401)

        uuid, _, key = credentials.partition(":")
        device = Device.query.filter_by(uuid=uuid.strip()).first()
        # Compare even when the device is unknown, so an unknown UUID and a
        # wrong key take the same path, and use compare_digest so neither
        # leaks by timing. A sha256 hexdigest is never "", so an unknown or
        # unpaired device can't match.
        expected = (device.device_key_hash if device else None) or ""
        if not hmac.compare_digest(expected, hash_device_key(key)):
            return _error("unauthorized", 401)
        if device.pairing_status != "paired":
            return _error("device is not paired", 403)

        g.device = device
        return view(*args, **kwargs)

    return wrapped


@device_api_bp.route("/devices/pair", methods=["POST"])
def pair():
    """Trade a pairing code for a device key. One time, per device."""
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip().upper()
    names = payload.get("camera_names") or []

    if not code:
        return _error("code is required", 400)
    if not isinstance(names, list) or not names:
        return _error("camera_names must be a non-empty list", 400)
    if len(names) > MAX_CAMERAS_PER_DEVICE:
        return _error(f"at most {MAX_CAMERAS_PER_DEVICE} cameras", 400)

    cleaned = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            return _error("camera names must be non-empty strings", 400)
        cleaned.append(name.strip())
    if len({n.lower() for n in cleaned}) != len(cleaned):
        return _error("camera names must be unique", 400)
    slugs = [make_camera_slug(n) for n in cleaned]
    if len(set(slugs)) != len(slugs):
        return _error("camera names must be unique", 400)

    device = Device.query.filter_by(pairing_code_hash=hash_pairing_code(code)).first()
    # A wrong code and an expired one are the same answer on purpose: an
    # unpaired caller learns nothing about which codes exist.
    if device is None or not device.pairing_code_is_usable:
        return _error("invalid or expired pairing code", 401)

    key = generate_device_key()
    device.device_key_hash = hash_device_key(key)
    device.pairing_status = "paired"
    # Burn the code — it is single use, and the device key replaces it.
    device.pairing_code_hash = None
    device.pairing_code_expires_at = None
    device.last_seen_at = _now()

    for name, slug in zip(cleaned, slugs):
        db.session.add(Camera(device_id=device.id, name=name, slug=slug))
    db.session.commit()

    return (
        jsonify(
            {
                "device_uuid": device.uuid,
                # Shown exactly once — only its hash is stored.
                "device_key": key,
                "establishment": device.establishment.name,
                "cameras": [
                    {"id": c.id, "name": c.name, "slug": c.slug}
                    for c in sorted(device.cameras, key=lambda c: c.id)
                ],
            }
        ),
        201,
    )


@device_api_bp.route("/clips", methods=["POST"])
@device_auth
def create_clip():
    """Record that a clip was exported. Phase 3 adds the upload itself."""
    payload = request.get_json(silent=True) or {}
    device = g.device

    camera_name = str(payload.get("camera_name", "")).strip()
    if not camera_name:
        return _error("camera_name is required", 400)
    camera = Camera.query.filter_by(device_id=device.id, name=camera_name).first()
    if camera is None:
        return _error(f"unknown camera '{camera_name}' for this device", 404)

    timestamps = {}
    for field in ("pressed_at", "start_ts", "end_ts"):
        parsed = _parse_ts(payload.get(field))
        if parsed is None:
            return _error(f"{field} must be an ISO 8601 timestamp", 400)
        timestamps[field] = parsed
    if timestamps["end_ts"] <= timestamps["start_ts"]:
        return _error("end_ts must be after start_ts", 400)

    numbers = {}
    for field in ("duration_seconds", "size_bytes"):
        value = payload.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return _error(f"{field} must be a non-negative integer", 400)
        numbers[field] = value

    local_filename = str(payload.get("local_filename") or "").strip() or None

    clip = Clip(
        establishment_id=device.establishment_id,
        camera_id=camera.id,
        local_filename=local_filename,
        pressed_at=timestamps["pressed_at"],
        start_ts=timestamps["start_ts"],
        end_ts=timestamps["end_ts"],
        duration_seconds=numbers["duration_seconds"],
        size_bytes=numbers["size_bytes"],
        # No s3_key yet — Phase 3 uploads the file and flips this to "ready".
        status="pending",
    )
    db.session.add(clip)
    device.last_seen_at = _now()
    db.session.commit()

    return jsonify({"clip_id": clip.id, "status": clip.status}), 201
