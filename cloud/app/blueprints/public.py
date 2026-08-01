from flask import Blueprint
from sqlalchemy import text

from ..extensions import db

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    # Phase 5 replaces this with the real marketing site.
    return "NO FLAGRA — cloud app scaffold. Marketing site lands in Phase 5."


@public_bp.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
