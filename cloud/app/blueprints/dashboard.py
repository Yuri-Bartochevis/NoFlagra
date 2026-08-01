from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import (
    INVITE_LIFETIME,
    Invite,
    Membership,
    generate_invite_token,
    hash_invite_token,
)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/app")


@dashboard_bp.before_request
@login_required
def load_establishment():
    # MVP: one membership per user. A multi-gym switcher comes later without
    # a schema change, since Membership is already user<->establishment.
    membership = Membership.query.filter_by(user_id=current_user.id).first()
    if membership is None:
        abort(404)
    g.establishment = membership.establishment
    g.membership = membership


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.membership.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


@dashboard_bp.route("/")
def home():
    # Phase 4 replaces this with the real black/yellow clip-library dashboard.
    return render_template("dashboard_placeholder.html", establishment=g.establishment)


@dashboard_bp.route("/team")
@role_required("admin")
def team():
    members = (
        Membership.query.filter_by(establishment_id=g.establishment.id)
        .join(Membership.user)
        .order_by(Membership.created_at)
        .all()
    )
    invites = (
        Invite.query.filter_by(establishment_id=g.establishment.id, status="pending")
        .order_by(Invite.created_at.desc())
        .all()
    )
    return render_template("team.html", members=members, invites=invites)


@dashboard_bp.route("/team/invite", methods=["POST"])
@role_required("admin")
def create_invite():
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "member")
    if role not in ("admin", "member"):
        role = "member"

    if not email or "@" not in email:
        flash("Enter a valid email.", "error")
        return redirect(url_for("dashboard.team"))

    if any(m.user.email == email for m in g.establishment.memberships):
        flash(f"{email} is already on this team.", "error")
        return redirect(url_for("dashboard.team"))

    existing = Invite.query.filter_by(
        establishment_id=g.establishment.id, email=email, status="pending"
    ).first()
    if existing is not None:
        flash(f"{email} already has a pending invite.", "error")
        return redirect(url_for("dashboard.team"))

    token = generate_invite_token()
    invite = Invite(
        establishment_id=g.establishment.id,
        email=email,
        role=role,
        token_hash=hash_invite_token(token),
        invited_by_user_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + INVITE_LIFETIME,
    )
    db.session.add(invite)
    db.session.commit()

    invite_link = url_for("auth.accept_invite", token=token, _external=True)
    flash(f"Invite created for {email}. Send them this link: {invite_link}", "success")
    return redirect(url_for("dashboard.team"))


@dashboard_bp.route("/team/invite/<int:invite_id>/revoke", methods=["POST"])
@role_required("admin")
def revoke_invite(invite_id):
    invite = Invite.query.filter_by(id=invite_id, establishment_id=g.establishment.id).first()
    if invite is None:
        abort(404)
    invite.status = "revoked"
    db.session.commit()
    flash(f"Invite for {invite.email} revoked.", "success")
    return redirect(url_for("dashboard.team"))
