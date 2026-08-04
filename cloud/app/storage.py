"""
Object storage for clips — Cloudflare R2, spoken to over the S3 API.

Why R2 and not S3: egress. S3 charges roughly $0.09/GB to send data out, R2
charges nothing. For a product whose growth loop is "someone shares a clip and
20 people watch it", metered egress means success is what bills you — at
original quality (~300 MB a clip) the bandwidth for one busy gym costs several
times what that gym pays us. R2 speaks the S3 API, so this module works
against either; only the endpoint changes.

Why presigned URLs rather than credentials on the Pi: a gym's Raspberry Pi
sits on a gym's Wi-Fi in a building we don't control. It gets a short-lived
URL that can write exactly one object, not a key that can read the bucket. It
also means the edge needs no AWS SDK at all — just an HTTP PUT.
"""

import os
from datetime import datetime

try:  # boto3 is only needed where uploads are configured
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - exercised by the "not configured" path
    boto3 = None
    Config = None

    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        pass


class StorageNotConfigured(RuntimeError):
    """Raised when an upload is attempted before R2 credentials exist."""


class StorageError(RuntimeError):
    """Anything the object store refused or failed to do."""


def _setting(name, default=""):
    return os.environ.get(name, default).strip()


def is_configured():
    """True when every piece needed to sign a URL is present."""
    return bool(
        boto3
        and _setting("R2_ENDPOINT")
        and _setting("R2_BUCKET")
        and _setting("R2_ACCESS_KEY_ID")
        and _setting("R2_SECRET_ACCESS_KEY")
    )


def bucket():
    return _setting("R2_BUCKET")


def _client():
    if not is_configured():
        missing = "boto3" if not boto3 else "R2_ENDPOINT / R2_BUCKET / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY"
        raise StorageNotConfigured(f"object storage is not set up ({missing})")
    return boto3.client(
        "s3",
        endpoint_url=_setting("R2_ENDPOINT"),
        aws_access_key_id=_setting("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_setting("R2_SECRET_ACCESS_KEY"),
        # R2 has no regions; "auto" is what Cloudflare's own docs use. SigV4
        # is required — R2 rejects the older signature versions outright.
        region_name=_setting("R2_REGION", "auto") or "auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def upload_ttl():
    """How long a PUT URL stays valid.

    Generous on purpose: a 300 MB original over a gym's upstream can take
    ten minutes, and a URL that expires mid-transfer wastes the whole upload.
    """
    return int(_setting("UPLOAD_URL_TTL", "3600") or 3600)


def playback_ttl():
    """How long a GET URL stays valid. Short — the share page mints a fresh
    one on every view, so a leaked URL stops working quickly."""
    return int(_setting("PLAYBACK_URL_TTL", "3600") or 3600)


def build_key(clip, filename):
    """Where a clip lives in the bucket.

    Grouped by establishment and camera so a gym's footage can be listed,
    lifecycle-ruled or deleted as one prefix, and dated so the bucket stays
    browsable by a human. The clip id keeps it unique even if two exports
    somehow share a filename.
    """
    camera = clip.camera
    establishment = clip.establishment
    when = clip.pressed_at or datetime.utcnow()
    safe = os.path.basename(filename or f"clip-{clip.id}.mp4")
    return (
        f"{establishment.slug}/{camera.slug}/"
        f"{when:%Y/%m}/{clip.id}-{safe}"
    )


def presign_put(key, content_type="video/mp4"):
    """A URL the Pi can PUT one object to, and nothing else."""
    try:
        return _client().generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket(), "Key": key, "ContentType": content_type},
            ExpiresIn=upload_ttl(),
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(str(exc)) from exc


def presign_get(key, download_as=None):
    """A short-lived URL for watching or downloading an object."""
    params = {"Bucket": bucket(), "Key": key}
    if download_as:
        params["ResponseContentDisposition"] = f'attachment; filename="{download_as}"'
    try:
        return _client().generate_presigned_url(
            "get_object", Params=params, ExpiresIn=playback_ttl()
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(str(exc)) from exc


def head(key):
    """Size of a stored object, or None if it isn't there.

    Used to verify an upload actually landed before a clip is marked ready —
    the Pi claiming success is not evidence that the bytes arrived.
    """
    try:
        response = _client().head_object(Bucket=bucket(), Key=key)
    except ClientError as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise StorageError(str(exc)) from exc
    except BotoCoreError as exc:
        raise StorageError(str(exc)) from exc
    return response.get("ContentLength")


def delete(key):
    """Best effort — a leftover object costs a fraction of a cent."""
    try:
        _client().delete_object(Bucket=bucket(), Key=key)
        return True
    except (BotoCoreError, ClientError, StorageNotConfigured):
        return False
