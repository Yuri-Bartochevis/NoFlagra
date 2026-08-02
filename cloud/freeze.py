"""
Render the public landing page to static HTML, for hosting somewhere that
can't run Python (GitHub Pages, S3, Netlify).

    python3 freeze.py            # -> dist/index.html (pt) + dist/en/index.html
    APP_BASE_URL=https://noflagra.onrender.com python3 freeze.py

Only the marketing page is frozen. /signup, /login, /invite and /app need a
running Flask app and a database; set APP_BASE_URL to point those links at a
real deployment, or leave it unset and they fall back to the quote anchor —
the funnel's primary CTA is WhatsApp, which needs no server at all.

Links come out relative on purpose: a GitHub Pages project site is served
from /<repo>/, so absolute "/..." paths would escape the site root.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path

DIST = Path(__file__).parent / "dist"
# Where /signup and /login should point. Without a deployment to aim at,
# send people to the quote section instead of a link that 404s.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "").rstrip("/")
FALLBACK = "#orcamento"


def _app_link(path):
    return f"{APP_BASE_URL}{path}" if APP_BASE_URL else FALLBACK


def rewrite(html, *, to_pt, to_en, to_home):
    """Point the server-rendered absolute URLs at static neighbours.

    Exact href="..." matches, longest first, so that rewriting "/" last
    can't clobber "/?lang=en" or "/#preco".
    """
    rules = [
        ('/?lang=pt', to_pt),
        ('/?lang=en', to_en),
        ('/#orcamento', '#orcamento'),
        ('/#preco', '#preco'),
        ('/signup', _app_link('/signup')),
        ('/login', _app_link('/login')),
        ('/', to_home),
    ]
    for old, new in rules:
        html = html.replace(f'href="{old}"', f'href="{new}"')
    return html


def build():
    fd, dbpath = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{dbpath}"

    from app import create_app
    from app.extensions import db

    app = create_app()
    app.config["TESTING"] = True

    try:
        with app.app_context():
            db.create_all()
            client = app.test_client()
            pt = client.get("/").get_data(as_text=True)
            en = client.get("/?lang=en").get_data(as_text=True)
    finally:
        os.remove(dbpath)

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "en").mkdir(parents=True)

    # From the root page, English lives one level down; from /en/, everything
    # else lives one level up.
    pt = rewrite(pt, to_pt="./", to_en="en/", to_home="./")
    en = rewrite(en, to_pt="../", to_en="./", to_home="../")
    en = en.replace('<html lang="en">', '<html lang="en">')
    pt = pt.replace('<html lang="en">', '<html lang="pt-BR">')

    (DIST / "index.html").write_text(pt, encoding="utf-8")
    (DIST / "en" / "index.html").write_text(en, encoding="utf-8")
    # Tells GitHub Pages not to run the output through Jekyll.
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    leftover = sorted(set(re.findall(r'href="(/[^"]*)"', pt + en)))
    if leftover:
        raise SystemExit(f"unrewritten absolute links remain: {leftover}")

    for f in (DIST / "index.html", DIST / "en" / "index.html"):
        print(f"  {f.relative_to(DIST.parent)}  {f.stat().st_size // 1024} KB")
    print(f"app links -> {APP_BASE_URL or FALLBACK + ' (no APP_BASE_URL set)'}")


if __name__ == "__main__":
    build()
