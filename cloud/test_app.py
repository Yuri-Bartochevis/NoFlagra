import os
import re
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import Establishment, Invite, Membership, User, hash_invite_token


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


def invite_token_from(resp):
    match = re.search(rb"/invite/([\w-]+)", resp.data)
    assert match, "no invite link found in response"
    return match.group(1).decode()


# ---- public site ----


def test_landing_page_renders_in_portuguese_by_default(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8").upper()
    assert "NUNCA PERCA O MOMENTO" in body
    assert "COMECE SUA ACADEMIA" in body


def test_landing_page_switches_to_english(client):
    resp = client.get("/?lang=en")
    assert resp.status_code == 200
    body = resp.data.upper()
    assert b"NEVER MISS THE MOMENT" in body
    assert b"START YOUR GYM" in body
    assert resp.headers["Set-Cookie"].startswith("lang=en")


def test_language_choice_is_remembered_via_cookie(client):
    client.get("/?lang=en")
    resp = client.get("/")
    assert b"NEVER MISS THE MOMENT" in resp.data.upper()


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
    assert "Já existe uma conta".encode() in resp.data


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


# ---- invites ----


def test_admin_can_invite_a_new_member(app, client):
    signup(client)  # yuri@example.com, admin of Yuri's BJJ
    resp = client.post(
        "/app/team/invite",
        data={"email": "student@example.com", "role": "member"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"student@example.com" in resp.data

    with app.app_context():
        invite = Invite.query.filter_by(email="student@example.com").first()
        assert invite is not None
        assert invite.role == "member"
        assert invite.status == "pending"


def test_non_admin_cannot_create_invites(app, client):
    signup(client)
    with app.app_context():
        establishment = Establishment.query.first()
        member = User(email="member@example.com", name="Member")
        member.set_password("supersecret1")
        _db.session.add(member)
        _db.session.flush()
        _db.session.add(Membership(user_id=member.id, establishment_id=establishment.id, role="member"))
        _db.session.commit()

    client.post("/logout")
    client.post("/login", data={"email": "member@example.com", "password": "supersecret1"})

    resp = client.post("/app/team/invite", data={"email": "x@example.com", "role": "member"})
    assert resp.status_code == 403


def test_invite_rejects_someone_already_on_the_team(client):
    signup(client)
    resp = client.post(
        "/app/team/invite", data={"email": "yuri@example.com", "role": "member"}, follow_redirects=True
    )
    assert b"already on this team" in resp.data


def test_invite_rejects_duplicate_pending_invite(client):
    signup(client)
    client.post("/app/team/invite", data={"email": "dup@example.com", "role": "member"})
    resp = client.post(
        "/app/team/invite", data={"email": "dup@example.com", "role": "member"}, follow_redirects=True
    )
    assert b"already has a pending invite" in resp.data


def test_new_person_can_accept_an_invite(app, client):
    signup(client)
    resp = client.post("/app/team/invite", data={"email": "student@example.com", "role": "member"}, follow_redirects=True)
    token = invite_token_from(resp)
    client.post("/logout")

    accept = client.get(f"/invite/{token}")
    assert accept.status_code == 200
    assert b"student@example.com" in accept.data

    resp = client.post(f"/invite/{token}", data={"name": "Student One", "password": "studentpass1"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/app/"

    with app.app_context():
        user = User.query.filter_by(email="student@example.com").first()
        assert user is not None
        membership = Membership.query.filter_by(user_id=user.id).first()
        assert membership.role == "member"
        invite = Invite.query.filter_by(email="student@example.com").first()
        assert invite.status == "accepted"

    dash = client.get("/app/")
    assert dash.status_code == 200


def test_existing_user_must_prove_password_to_accept_invite(app, client):
    signup(client, email="owner@example.com", gym_name="Gym A")
    client.post("/logout")
    signup(client, email="pro@example.com", gym_name="Gym B", password="theirrealpassword")
    client.post("/logout")

    client.post("/login", data={"email": "owner@example.com", "password": "supersecret1"})
    resp = client.post("/app/team/invite", data={"email": "pro@example.com", "role": "admin"}, follow_redirects=True)
    token = invite_token_from(resp)
    client.post("/logout")

    wrong = client.post(f"/invite/{token}", data={"password": "wrongpassword"})
    assert wrong.status_code == 401

    with app.app_context():
        user = User.query.filter_by(email="pro@example.com").first()
        assert Membership.query.filter_by(user_id=user.id).count() == 1  # not yet added

    right = client.post(f"/invite/{token}", data={"password": "theirrealpassword"})
    assert right.status_code == 302
    assert right.headers["Location"] == "/app/"

    with app.app_context():
        user = User.query.filter_by(email="pro@example.com").first()
        memberships = Membership.query.filter_by(user_id=user.id).all()
        assert len(memberships) == 2
        roles = {m.establishment.name: m.role for m in memberships}
        assert roles["Gym B"] == "admin"  # from their own signup
        assert roles["Gym A"] == "admin"  # from the invite


def test_admin_can_revoke_a_pending_invite(app, client):
    signup(client)
    resp = client.post("/app/team/invite", data={"email": "student@example.com", "role": "member"}, follow_redirects=True)
    token = invite_token_from(resp)

    with app.app_context():
        invite = Invite.query.filter_by(email="student@example.com").first()
        invite_id = invite.id

    revoke = client.post(f"/app/team/invite/{invite_id}/revoke", follow_redirects=True)
    assert revoke.status_code == 200
    assert b"revoked" in revoke.data

    client.post("/logout")
    accept = client.get(f"/invite/{token}")
    assert accept.status_code == 404


def test_expired_invite_cannot_be_accepted(app, client):
    signup(client)
    with app.app_context():
        establishment = Establishment.query.first()
        admin = User.query.first()
        token = "expired-token-for-test"
        invite = Invite(
            establishment_id=establishment.id,
            email="late@example.com",
            role="member",
            token_hash=hash_invite_token(token),
            invited_by_user_id=admin.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        _db.session.add(invite)
        _db.session.commit()

    client.post("/logout")
    resp = client.get(f"/invite/{token}")
    assert resp.status_code == 404
