import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

INVITE_LIFETIME = timedelta(days=7)
PAIRING_CODE_LIFETIME = timedelta(minutes=15)
# Excludes 0/O/1/I so a code read aloud over the phone isn't ambiguous.
PAIRING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    memberships = db.relationship("Membership", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Establishment(db.Model):
    __tablename__ = "establishments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    timezone = db.Column(db.String(64), nullable=False, default="UTC")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    memberships = db.relationship("Membership", back_populates="establishment")
    invites = db.relationship("Invite", back_populates="establishment")
    devices = db.relationship("Device", back_populates="establishment")
    clips = db.relationship("Clip", back_populates="establishment")


class Membership(db.Model):
    __tablename__ = "memberships"
    __table_args__ = (
        db.UniqueConstraint("user_id", "establishment_id", name="uq_membership_user_establishment"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    establishment_id = db.Column(db.Integer, db.ForeignKey("establishments.id"), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="member")  # "admin" | "member"
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    user = db.relationship("User", back_populates="memberships")
    establishment = db.relationship("Establishment", back_populates="memberships")


class Invite(db.Model):
    __tablename__ = "invites"

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("establishments.id"), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="member")
    token_hash = db.Column(db.String(255), nullable=False)
    invited_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")  # pending|accepted|expired|revoked
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    establishment = db.relationship("Establishment", back_populates="invites")
    invited_by = db.relationship("User")

    @property
    def is_usable(self):
        expires = self.expires_at
        if expires.tzinfo is None:
            # SQLite drops tzinfo on round-trip even with DateTime(timezone=True);
            # everything we write is UTC, so a naive value here means UTC.
            expires = expires.replace(tzinfo=timezone.utc)
        return self.status == "pending" and expires > _now()


class Device(db.Model):
    __tablename__ = "devices"
    __table_args__ = (
        # One device per account, for now. Dropping this constraint is the
        # whole migration needed to support several devices per gym later —
        # nothing else about this model assumes a single device.
        db.UniqueConstraint("establishment_id", name="uq_device_establishment"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # Public identifier — pairing responses, API auth, and (later) S3/QR
    # codes use this, never the numeric id.
    uuid = db.Column(db.String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    establishment_id = db.Column(db.Integer, db.ForeignKey("establishments.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    device_key_hash = db.Column(db.String(255), nullable=True)
    pairing_status = db.Column(db.String(32), nullable=False, default="pending")  # pending|paired|revoked
    pairing_code_hash = db.Column(db.String(255), nullable=True)
    pairing_code_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    establishment = db.relationship("Establishment", back_populates="devices")
    cameras = db.relationship("Camera", back_populates="device")

    @property
    def pairing_code_is_usable(self):
        expires = self.pairing_code_expires_at
        if expires is None:
            return False
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return self.pairing_status == "pending" and expires > _now()


class Camera(db.Model):
    __tablename__ = "cameras"
    __table_args__ = (
        db.UniqueConstraint("device_id", "name", name="uq_camera_device_name"),
        db.UniqueConstraint("device_id", "slug", name="uq_camera_device_slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)  # matches Frigate's camera name
    slug = db.Column(db.String(255), nullable=False)  # used in the S3 key
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    device = db.relationship("Device", back_populates="cameras")
    clips = db.relationship("Clip", back_populates="camera")


class Clip(db.Model):
    __tablename__ = "clips"
    __table_args__ = (db.Index("ix_clips_establishment_pressed_at", "establishment_id", "pressed_at"),)

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("establishments.id"), nullable=False)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"), nullable=False)
    # Set by Phase 3's upload step — a Phase 2 clip has metadata but no S3
    # key yet, so this starts out empty.
    s3_key = db.Column(db.String(512), nullable=True)
    s3_thumb_key = db.Column(db.String(512), nullable=True)
    # Filename on the Pi's own disk (see clip_name() in edge/receiver/app.py)
    # — lets playback and the Phase 3 uploader find the file before/without
    # an s3_key.
    local_filename = db.Column(db.String(255), nullable=True)
    pressed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    start_ts = db.Column(db.DateTime(timezone=True), nullable=False)
    end_ts = db.Column(db.DateTime(timezone=True), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    size_bytes = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")  # pending|uploading|ready|failed
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    establishment = db.relationship("Establishment", back_populates="clips")
    camera = db.relationship("Camera", back_populates="clips")


def _slugify(name: str) -> str:
    base = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return base


def make_slug(name: str) -> str:
    base = _slugify(name)
    suffix = secrets.token_hex(3)
    return f"{base}-{suffix}" if base else suffix


def make_camera_slug(name: str) -> str:
    # No random suffix: uniqueness is scoped to one device's handful of
    # cameras (enforced by uq_camera_device_slug), not global like
    # establishment slugs, and a plain slug is what shows up in the S3 path.
    return _slugify(name) or secrets.token_hex(3)


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    # Sha256 (no salt) is fine here: the token is 32 bytes of CSPRNG entropy,
    # not a low-entropy password, so a fast deterministic hash — which lets
    # us look an invite up by token_hash directly — is the right trade-off.
    return hashlib.sha256(token.encode()).hexdigest()


def generate_device_key() -> str:
    return secrets.token_urlsafe(32)


def hash_device_key(key: str) -> str:
    # Same rationale as hash_invite_token above: 32 bytes of CSPRNG entropy,
    # so a fast deterministic hash that supports a direct lookup is the
    # right trade-off.
    return hashlib.sha256(key.encode()).hexdigest()


def generate_pairing_code() -> str:
    return "".join(secrets.choice(PAIRING_CODE_ALPHABET) for _ in range(8))


def hash_pairing_code(code: str) -> str:
    # Unlike a device key, this is short enough to be guessable by brute
    # force if the pairing endpoint had no other defenses — PAIRING_CODE_LIFETIME
    # (15 min) bounds the window; rate limiting the endpoint is still open,
    # see docs/infrastructure.md. Sha256 here is just "don't store it in the
    # clear," not the thing doing the real protecting.
    return hashlib.sha256(code.encode()).hexdigest()
