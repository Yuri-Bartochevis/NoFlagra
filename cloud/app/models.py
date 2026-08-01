import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

INVITE_LIFETIME = timedelta(days=7)


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

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("establishments.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    camera_name = db.Column(db.String(255), nullable=False)
    device_key_hash = db.Column(db.String(255), nullable=False)
    pairing_status = db.Column(db.String(32), nullable=False, default="paired")
    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    establishment = db.relationship("Establishment", back_populates="devices")


class Clip(db.Model):
    __tablename__ = "clips"
    __table_args__ = (db.Index("ix_clips_establishment_pressed_at", "establishment_id", "pressed_at"),)

    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("establishments.id"), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=False)
    s3_key = db.Column(db.String(512), nullable=False)
    s3_thumb_key = db.Column(db.String(512), nullable=True)
    pressed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    start_ts = db.Column(db.DateTime(timezone=True), nullable=False)
    end_ts = db.Column(db.DateTime(timezone=True), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False)
    size_bytes = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")  # pending|uploading|ready|failed
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    establishment = db.relationship("Establishment", back_populates="clips")


def make_slug(name: str) -> str:
    base = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    suffix = secrets.token_hex(3)
    return f"{base}-{suffix}" if base else suffix


def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invite_token(token: str) -> str:
    # Sha256 (no salt) is fine here: the token is 32 bytes of CSPRNG entropy,
    # not a low-entropy password, so a fast deterministic hash — which lets
    # us look an invite up by token_hash directly — is the right trade-off.
    return hashlib.sha256(token.encode()).hexdigest()
