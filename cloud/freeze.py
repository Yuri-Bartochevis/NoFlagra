"""
Render the public marketing pages to static HTML, for hosting somewhere that
can't run Python (GitHub Pages, S3, Netlify).

    python3 freeze.py            # -> dist/, both locales
    APP_BASE_URL=https://noflagra.onrender.com python3 freeze.py
    SITE_URL=https://user.github.io/NoFlagra python3 freeze.py

Only the marketing pages are frozen. /signup, /login, /invite and /app need a
running Flask app and a database; set APP_BASE_URL to point those links at a
real deployment, or leave it unset and they fall back to the quote anchor —
the funnel's primary CTA is WhatsApp, which needs no server at all.

SITE_URL sets the absolute origin baked into canonical and og:image. Point it
at wherever this frozen copy is actually served: og:image must be an absolute
URL, and a scraper that can't fetch it shows no preview card at all.

Links come out relative on purpose: a GitHub Pages project site is served
from /<repo>/, so absolute "/..." paths would escape the site root.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
DIST = HERE / "dist"
STATIC_SRC = HERE / "app" / "static"

# Where /signup and /login should point. Without a deployment to aim at,
# send people to the quote section instead of a link that 404s.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "").rstrip("/")
FALLBACK = "#orcamento"

# (route on the Flask app, directory under dist/). "" is the site root.
PAGES = [
    ("/", ""),
    ("/sobre", "sobre"),
    ("/privacidade", "privacidade"),
    ("/termos", "termos"),
]

# Locale -> the directory it lives under. Portuguese is the default and sits
# at the root; English nests one level down.
LOCALE_DIRS = {"pt": "", "en": "en"}


def _app_link(path, fallback):
    """Where /signup and /login should point in the frozen copy.

    Without a running app to aim at we fall back to the quote section — which
    only exists on the home page, so the fallback has to be resolved relative
    to the page being rendered rather than emitted as a bare "#orcamento"
    that dead-ends on /sobre.
    """
    return f"{APP_BASE_URL}{path}" if APP_BASE_URL else fallback


def _out_path(locale, page_dir):
    """dist/<locale>/<page>/index.html, skipping empty segments."""
    parts = [p for p in (LOCALE_DIRS[locale], page_dir) if p]
    return DIST.joinpath(*parts, "index.html")


def _prefix(locale, page_dir):
    """Relative path back up to the site root from a page's own directory."""
    depth = len([p for p in (LOCALE_DIRS[locale], page_dir) if p])
    return "../" * depth


def _home(locale, prefix):
    """Relative link to a locale's home page from somewhere at `prefix`."""
    directory = LOCALE_DIRS[locale]
    return f"{prefix}{directory}/" if directory else (prefix or "./")


def rewrite(html, *, locale, page_dir, route):
    """Turn the app's absolute URLs into links between static neighbours.

    Rules are applied longest-first so that rewriting "/" last can't clobber
    "/sobre" or "/?lang=en", and each is matched as a complete attribute
    value rather than a substring.
    """
    prefix = _prefix(locale, page_dir)
    pt_home = _home("pt", prefix)
    en_home = _home("en", prefix)

    def page_link(target_locale, target_dir):
        base = _home(target_locale, prefix)
        return f"{base}{target_dir}/" if target_dir else base

    rules = []

    # The language switch renders href="<this route>?lang=xx" — it has to
    # land on this same page in the other locale, not on the home page.
    lang_suffix = "" if route == "/" else route
    rules.append((f"{lang_suffix}/?lang=pt" if route == "/" else f"{route}?lang=pt",
                  page_link("pt", page_dir)))
    rules.append((f"{lang_suffix}/?lang=en" if route == "/" else f"{route}?lang=en",
                  page_link("en", page_dir)))

    # Cross-page links, longest path first.
    for _route, _dir in sorted(PAGES, key=lambda p: -len(p[0])):
        if _dir:
            rules.append((_route, page_link(locale, _dir)))

    quote_anchor = f"{_home(locale, prefix)}#orcamento" if page_dir else "#orcamento"
    rules += [
        ("/#orcamento", quote_anchor),
        ("/#preco", f"{_home(locale, prefix)}#preco"),
        ("/signup", _app_link("/signup", quote_anchor)),
        ("/login", _app_link("/login", quote_anchor)),
        ("/", _home(locale, prefix)),
    ]

    for old, new in rules:
        html = html.replace(f'href="{old}"', f'href="{new}"')

    # Assets are referenced from href/src/poster alike, so rewrite the prefix
    # once rather than per-attribute.
    html = html.replace('"/static/', f'"{prefix}static/')
    return html


def build():
    fd, dbpath = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{dbpath}"

    from app import create_app
    from app.extensions import db

    app = create_app()
    app.config["TESTING"] = True

    rendered = {}
    try:
        with app.app_context():
            db.create_all()
            client = app.test_client()
            for route, page_dir in PAGES:
                for locale in LOCALE_DIRS:
                    sep = "&" if "?" in route else "?"
                    url = f"{route}{sep}lang={locale}"
                    resp = client.get(url)
                    if resp.status_code != 200:
                        raise SystemExit(f"{url} returned {resp.status_code}")
                    rendered[(locale, page_dir, route)] = resp.get_data(as_text=True)
    finally:
        os.remove(dbpath)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    # The video, poster, OG images and icons all live here; without them the
    # frozen pages render with broken media and no social preview.
    shutil.copytree(STATIC_SRC, DIST / "static")

    for (locale, page_dir, route), html in rendered.items():
        html = rewrite(html, locale=locale, page_dir=page_dir, route=route)
        out = _out_path(locale, page_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")

    # Tells GitHub Pages not to run the output through Jekyll, which would
    # otherwise strip files and directories beginning with an underscore.
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    written = sorted(DIST.rglob("index.html"))
    for f in written:
        print(f"  {f.relative_to(DIST.parent)}  {f.stat().st_size // 1024} KB")

    # Any absolute path left over would escape a project-site subpath. Skip
    # canonical/og:image, which are absolute origins on purpose.
    leftover = set()
    for f in written:
        text = f.read_text(encoding="utf-8")
        leftover |= set(re.findall(r'(?:href|src|poster)="(/[^"]*)"', text))
    if leftover:
        raise SystemExit(f"unrewritten absolute links remain: {sorted(leftover)}")

    print(f"  static/  {sum(p.stat().st_size for p in (DIST / 'static').iterdir()) // 1024} KB")
    print(f"app links -> {APP_BASE_URL or FALLBACK + ' (no APP_BASE_URL set)'}")
    print(f"site origin -> {app.config['SITE_URL']}")


if __name__ == "__main__":
    build()
