from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from ..extensions import db
from ..i18n import t
from ..models import Establishment, Invite, Membership, User, hash_invite_token, make_slug

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    gym_name = request.form.get("gym_name", "").strip()
    password = request.form.get("password", "")

    errors = []
    if not name:
        errors.append(t("err_name_required"))
    if not email or "@" not in email:
        errors.append(t("err_email_invalid"))
    if not gym_name:
        errors.append(t("err_gym_required"))
    if len(password) < 8:
        errors.append(t("err_password_short"))
    if email and User.query.filter_by(email=email).first():
        errors.append(t("err_email_taken"))

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("signup.html", name=name, email=email, gym_name=gym_name), 400

    user = User(email=email, name=name)
    user.set_password(password)
    establishment = Establishment(name=gym_name, slug=make_slug(gym_name))
    membership = Membership(user=user, establishment=establishment, role="admin")

    db.session.add_all([user, establishment, membership])
    db.session.commit()

    login_user(user)
    return redirect(url_for("dashboard.home"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        flash(t("err_wrong_login"), "error")
        return render_template("login.html", email=email), 401

    login_user(user)
    return redirect(url_for("dashboard.home"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("public.index"))


def _add_member(invite, user):
    membership = Membership(user=user, establishment=invite.establishment, role=invite.role)
    invite.status = "accepted"
    db.session.add(membership)
    db.session.commit()


@auth_bp.route("/invite/<token>", methods=["GET", "POST"])
def accept_invite(token):
    invite = Invite.query.filter_by(token_hash=hash_invite_token(token)).first()
    if invite is None or not invite.is_usable:
        abort(404)

    existing_user = User.query.filter_by(email=invite.email).first()

    # Already logged in as the invited person — nothing left to prove, just join.
    if current_user.is_authenticated and current_user.email == invite.email:
        _add_member(invite, current_user)
        flash(f"You're in — welcome to {invite.establishment.name}.", "success")
        return redirect(url_for("dashboard.home"))

    if existing_user is not None:
        # Never auto-log-in an existing account from an invite link alone —
        # that would let anyone who knows a person's email add them to a gym
        # and get logged in as them. Require their real password.
        if request.method == "GET":
            return render_template("invite_accept.html", invite=invite, existing_account=True)

        password = request.form.get("password", "")
        if not existing_user.check_password(password):
            flash(t("err_wrong_login"), "error")
            return render_template("invite_accept.html", invite=invite, existing_account=True), 401

        _add_member(invite, existing_user)
        login_user(existing_user)
        flash(f"You're in — welcome to {invite.establishment.name}.", "success")
        return redirect(url_for("dashboard.home"))

    # No account for this email yet — same shape as signup, minus choosing a gym.
    if request.method == "GET":
        return render_template("invite_accept.html", invite=invite, existing_account=False)

    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")

    errors = []
    if not name:
        errors.append(t("err_name_required"))
    if len(password) < 8:
        errors.append(t("err_password_short"))

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template("invite_accept.html", invite=invite, existing_account=False, name=name), 400

    user = User(email=invite.email, name=name)
    user.set_password(password)
    db.session.add(user)
    _add_member(invite, user)
    login_user(user)
    flash(f"You're in — welcome to {invite.establishment.name}.", "success")
    return redirect(url_for("dashboard.home"))
