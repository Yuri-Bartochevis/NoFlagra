from flask import Blueprint, render_template
from sqlalchemy import text

from ..extensions import db

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    return render_template("index.html")


@public_bp.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
