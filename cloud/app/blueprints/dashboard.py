from functools import wraps

from flask import Blueprint, abort, g, render_template
from flask_login import current_user, login_required

from ..models import Membership

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
