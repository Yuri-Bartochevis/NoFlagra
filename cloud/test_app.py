import os
import tempfile

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import Membership, User


@pytest.fixture
def app():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"

    application = create_app()
    application.config["TESTING"] = True

    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()

    os.remove(path)


@pytest.fixture
def client(app):
    return app.test_client()


def signup(client, email="yuri@example.com", password="supersecret1", gym_name="Yuri's BJJ", name="Yuri"):
    return client.post(
        "/signup",
        data={"name": name, "email": email, "gym_name": gym_name, "password": password},
    )


# ---- public site ----


def test_landing_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.upper()
    assert b"NEVER MISS THE MOMENT" in body
    assert b"START YOUR GYM" in body


def test_health_reports_database_reachable(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "database": "reachable"}


# ---- signup ----


def test_signup_creates_account_and_redirects_to_dashboard(client):
    resp = signup(client)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/app/"


def test_signup_logs_the_new_user_in(client):
    signup(client)
    dash = client.get("/app/")
    assert dash.status_code == 200
    assert b"Yuri&#39;s BJJ" in dash.data or b"Yuri's BJJ" in dash.data


def test_signup_creates_one_establishment_with_an_admin_membership(app, client):
    signup(client)
    with app.app_context():
        user = User.query.filter_by(email="yuri@example.com").first()
        assert user is not None
        assert user.check_password("supersecret1")

        membership = Membership.query.filter_by(user_id=user.id).first()
        assert membership is not None
        assert membership.role == "admin"
        assert membership.establishment.name == "Yuri's BJJ"


def test_signup_rejects_duplicate_email(client):
    signup(client)
    resp = signup(client, name="Someone Else", gym_name="Another Gym")
    assert resp.status_code == 400
    assert b"already exists" in resp.data


def test_signup_rejects_short_password(client):
    resp = signup(client, password="short")
    assert resp.status_code == 400


# ---- login / logout ----


def test_login_with_correct_password_succeeds(client):
    signup(client)
    client.post("/logout")
    resp = client.post("/login", data={"email": "yuri@example.com", "password": "supersecret1"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/app/"


def test_login_with_wrong_password_is_rejected(client):
    signup(client)
    client.post("/logout")
    resp = client.post("/login", data={"email": "yuri@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_logout_ends_the_session(client):
    signup(client)
    client.post("/logout")
    dash = client.get("/app/")
    assert dash.status_code == 302
    assert "/login" in dash.headers["Location"]


# ---- dashboard gating ----


def test_dashboard_requires_login(client):
    resp = client.get("/app/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_two_gyms_cannot_see_each_others_establishment(app, client):
    signup(client, email="a@example.com", gym_name="Gym A")
    client.post("/logout")
    signup(client, email="b@example.com", gym_name="Gym B")

    dash = client.get("/app/")
    assert b"Gym B" in dash.data
    assert b"Gym A" not in dash.data
