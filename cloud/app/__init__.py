import os

from flask import Flask, request

from .extensions import db, login_manager, migrate
from .i18n import LOCALES, get_locale, t


DEV_SECRET_KEY = "dev-insecure-change-me"

# Locale code -> the BCP 47 tag that goes in <html lang> and og:locale.
HTML_LANG = {"pt": "pt-BR", "en": "en"}


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
    # Absolute origin, no trailing slash. og:image and canonical have to be
    # absolute URLs — a relative one is silently dropped by WhatsApp and
    # every other scraper. The landing page is served from two places (this
    # app and the frozen GitHub Pages copy), so both point canonical at the
    # same origin rather than competing for the same keywords.
    app.config["SITE_URL"] = os.environ.get("SITE_URL", "https://noflagra.onrender.com").rstrip("/")
    # Shown in the footer once the company is registered; hidden while empty
    # rather than rendering a placeholder that looks like a real number.
    app.config["COMPANY_CNPJ"] = os.environ.get("COMPANY_CNPJ", "")

    db.init_app(app)
    migrate.init_app(app, db)

    @app.context_processor
    def inject_i18n():
        locale = get_locale()
        return {
            "t": t,
            "locale": locale,
            # BCP 47 for the <html lang> attribute — "pt" alone is understood
            # but "pt-BR" is what screen readers need to pick the right voice.
            "html_lang": HTML_LANG[locale],
            "whatsapp_number": app.config["WHATSAPP_NUMBER"],
            "site_url": app.config["SITE_URL"],
            "company_cnpj": app.config["COMPANY_CNPJ"],
        }

    @app.template_global()
    def static_exists(filename):
        """True when app/static/<filename> is actually on disk.

        Lets a template hold a slot for an asset that hasn't been shot yet
        (the button photo) without rendering a broken image in the meantime —
        drop the file in and the section appears on its own.
        """
        return os.path.isfile(os.path.join(app.static_folder, filename))

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
    from .blueprints.share import share_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(device_api_bp)
    app.register_blueprint(share_bp)

    return app
