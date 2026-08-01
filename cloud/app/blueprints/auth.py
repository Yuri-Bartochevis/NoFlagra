from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user

from ..extensions import db
from ..models import Establishment, Membership, User, make_slug

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
        errors.append("Enter your name.")
    if not email or "@" not in email:
        errors.append("Enter a valid email.")
    if not gym_name:
        errors.append("Enter your gym's name.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if email and User.query.filter_by(email=email).first():
        errors.append("An account with that email already exists — log in instead.")

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
        flash("Wrong email or password.", "error")
        return render_template("login.html", email=email), 401

    login_user(user)
    return redirect(url_for("dashboard.home"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("public.index"))
