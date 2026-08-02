import os

from flask import Flask, request

from .extensions import db, login_manager, migrate
from .i18n import LOCALES, get_locale, t


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "postgresql://noflagra:noflagra@localhost:5432/noflagra"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-insecure-change-me")
    # Digits only, with country + area code — wa.me rejects punctuation.
    app.config["WHATSAPP_NUMBER"] = os.environ.get("WHATSAPP_NUMBER", "5511989449987")

    db.init_app(app)
    migrate.init_app(app, db)

    @app.context_processor
    def inject_i18n():
        return {
            "t": t,
            "locale": get_locale(),
            "whatsapp_number": app.config["WHATSAPP_NUMBER"],
        }

    @app.after_request
    def remember_locale(response):
        lang = request.args.get("lang")
        if lang in LOCALES:
            response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
        return response

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from . import models  # noqa: F401 — registers models with SQLAlchemy metadata

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    from .blueprints.auth import auth_bp
    from .blueprints.dashboard import dashboard_bp
    from .blueprints.public import public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    return app
