import os

from flask import Flask

from .extensions import db


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "postgresql://noflagra:noflagra@localhost:5432/noflagra"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    from .blueprints.public import public_bp

    app.register_blueprint(public_bp)

    # Phase 1 adds: app_bp (mounted at /app), login_manager.init_app(app)

    return app
