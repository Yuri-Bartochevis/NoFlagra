from flask import Blueprint, Response, current_app, redirect, render_template, url_for
from sqlalchemy import text

from .. import HTML_LANG
from ..extensions import db
from ..i18n import LOCALES, get_locale
from ..legal import LEGAL_DRAFT_NOTICE, PRIVACY, TERMS

public_bp = Blueprint("public", __name__)

# Paths worth handing to a crawler. Everything else on the public side is
# either a form (/signup, /login) or gated (/app/*), and belongs out of the
# index — see robots() below.
SITEMAP_ENDPOINTS = ("public.index", "public.about", "public.privacy", "public.terms")


@public_bp.route("/")
def index():
    return render_template("index.html")


@public_bp.route("/sobre")
def about():
    return render_template("about.html")


def _legal(pages):
    """Render a legal page in the visitor's locale.

    Falls back to Portuguese for any locale the copy hasn't been translated
    into yet, matching how t() degrades in i18n.py.
    """
    locale = get_locale()
    return render_template(
        "legal.html",
        page=pages.get(locale, pages["pt"]),
        draft_notice=LEGAL_DRAFT_NOTICE.get(locale, LEGAL_DRAFT_NOTICE["pt"]),
    )


@public_bp.route("/privacidade")
def privacy():
    return _legal(PRIVACY)


@public_bp.route("/termos")
def terms():
    return _legal(TERMS)


# English aliases. Kept as redirects rather than second routes on the same
# view so url_for() stays unambiguous and each page has exactly one canonical
# URL — two live paths serving identical copy is a duplicate-content problem.
for _alias, _target in (("/about", "public.about"),
                        ("/privacy", "public.privacy"),
                        ("/terms", "public.terms")):
    public_bp.add_url_rule(
        _alias,
        endpoint=f"{_target.split('.')[1]}_alias",
        view_func=(lambda target=_target: redirect(url_for(target), code=301)),
    )


@public_bp.route("/robots.txt")
def robots():
    site = current_app.config["SITE_URL"]
    # /app/ is behind a login and /signup, /login, /invite are forms — none
    # of them belong in a search index, and crawling them just burns budget
    # that should go to the marketing pages.
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /app/\n"
        "Disallow: /signup\n"
        "Disallow: /login\n"
        "Disallow: /invite/\n"
        f"\nSitemap: {site}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@public_bp.route("/sitemap.xml")
def sitemap():
    site = current_app.config["SITE_URL"]
    urls = []
    for endpoint in SITEMAP_ENDPOINTS:
        path = url_for(endpoint)
        # One <url> per page, with an hreflang alternate per locale so Google
        # serves the Portuguese page to Brazil and the English one elsewhere
        # instead of treating them as duplicates.
        alts = "".join(
            f'<xhtml:link rel="alternate" hreflang="{HTML_LANG[loc]}" '
            f'href="{site}{path}?lang={loc}"/>'
            for loc in LOCALES
        )
        urls.append(f"<url><loc>{site}{path}</loc>{alts}</url>")

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
        f"{''.join(urls)}"
        "</urlset>"
    )
    return Response(body, mimetype="application/xml")


@public_bp.route("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
