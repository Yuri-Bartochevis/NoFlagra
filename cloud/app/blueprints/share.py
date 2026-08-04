"""
Public clip sharing — the half of the product a student actually sees.

A share link is deliberately dumb: no login, no app, no account. Someone gets
a URL in a WhatsApp group and it plays. That's the whole growth loop, so the
page has to survive being opened by a stranger on a phone on mobile data.

The token in the URL is random (see generate_share_token) rather than the row
id, because a sequential id in a public link would let anyone enumerate every
clip every gym has ever shared.

The page never embeds a storage URL directly. It points <video> at
/c/<token>/video, which mints a short-lived presigned GET on each request and
redirects. So a copied page URL keeps working forever, while any storage URL
scraped out of it stops working within the hour.
"""

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
)

from .. import storage
from ..models import Clip

share_bp = Blueprint("share", __name__)


def _clip_or_404(token):
    clip = Clip.query.filter_by(share_token=token).first()
    # A clip that exists but isn't ready is a 404 to the public: "not shared"
    # and "never existed" should look the same from outside.
    if clip is None or not clip.is_shared:
        abort(404)
    return clip


@share_bp.route("/c/<token>")
def view(token):
    clip = _clip_or_404(token)
    return render_template(
        "share.html",
        clip=clip,
        establishment=clip.establishment,
        minutes=max(1, round(clip.duration_seconds / 60)),
        size_mb=round((clip.size_bytes or 0) / 1048576),
    )


@share_bp.route("/c/<token>/video")
def video(token):
    """Redirect to a freshly signed storage URL.

    A redirect rather than proxying the bytes: streaming 300 MB through this
    app would tie up a worker for the length of the video, and the free tier
    has two. The browser talks to R2 directly and we stay out of the way —
    which is also what makes range requests and seeking work properly.
    """
    clip = _clip_or_404(token)
    if not storage.is_configured():
        abort(503)

    download = request.args.get("dl") == "1"
    try:
        url = storage.presign_get(
            clip.s3_key,
            download_as=clip.local_filename if download else None,
        )
    except storage.StorageError:
        current_app.logger.exception("could not sign a playback URL for clip %s", clip.id)
        abort(502)
    return redirect(url, code=302)
