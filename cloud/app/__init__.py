import os

from flask import Flask, request

from .extensions import db, login_manager, migrate
from .i18n import LOCALES, get_locale, t


DEV_SECRET_KEY = "dev-insecure-change-me"


def _database_url():
    url = os.environ.get("DATABASE_URL", "postgresql://noflagra:noflagra@localhost:5432/noflagra")
    # Render, Railway and Heroku all hand out "postgres://", a scheme
    # SQLAlchemy 2.x dropped — without this the app dies at boot with
    # "Can't load plugin: sqlalchemy.dialects:postgres".
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", DEV_SECRET_KEY)
    if app.config["SECRET_KEY"] == DEV_SECRET_KEY:
        # This key signs session cookies. Left at the default on a public
        # deploy, anyone who reads this repo can forge a session for any
        # user id — set FLASK_SECRET_KEY to a real random value.
        app.logger.warning("FLASK_SECRET_KEY is unset — using the insecure dev default.")
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
    from .blueprints.device_api import device_api_bp
    from .blueprints.public import public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(device_api_bp)

    return app
