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


# ---- lang attribute, meta and social cards ----


def test_portuguese_pages_declare_pt_br(client):
    # Regression: base.html used to hardcode lang="en" for every locale,
    # so screen readers read Portuguese copy with an English voice.
    assert b'<html lang="pt-BR">' in client.get("/").data
    assert b'<html lang="en">' in client.get("/?lang=en").data


def test_pages_carry_a_description_and_canonical(client):
    body = client.get("/").data.decode("utf-8")
    assert 'name="description"' in body
    assert 'rel="canonical"' in body


def test_social_card_is_absolute_and_locale_specific(client):
    # og:image must be absolute — WhatsApp silently drops a relative one,
    # and the funnel's main path is someone forwarding this link.
    pt = client.get("/").data.decode("utf-8")
    en = client.get("/?lang=en").data.decode("utf-8")
    assert 'property="og:image" content="https://' in pt
    assert "/static/og.jpg" in pt
    assert "/static/og-en.jpg" in en
    assert 'name="twitter:card" content="summary_large_image"' in pt


def test_copy_presents_the_clip_length_as_a_default_not_a_fixed_number(client):
    # The window is LOOKBACK_SECONDS on the receiver, set per gym at install.
    # Copy may quote 10 minutes as the default, but must say somewhere that
    # it can be changed — otherwise the site promises a fixed product.
    pt = client.get("/").data.decode("utf-8")
    en = client.get("/?lang=en").data.decode("utf-8")
    assert "padrão" in pt and "ajusta" in pt
    assert "default" in en and "install" in en


def test_showcase_uses_the_real_mat_footage(client):
    body = client.get("/").data.decode("utf-8")
    assert "mat-demo.mp4" in body
    assert "mat-poster.jpg" in body


def test_static_exists_gates_the_optional_photo_slots(app):
    # The slots must not render a broken <img> for an asset that isn't there.
    from app import create_app  # noqa: F401 — documents where the helper lives

    exists = app.jinja_env.globals["static_exists"]
    assert exists("mat-poster.jpg") is True
    assert exists("not-shot-yet.jpg") is False


def test_button_photo_renders_with_its_caption_in_both_locales(client):
    pt = client.get("/").data.decode("utf-8")
    en = client.get("/?lang=en").data.decode("utf-8")
    assert "button.jpg" in pt and "button.jpg" in en
    assert "não no seu bolso" in pt
    assert "not in your pocket" in en


def test_mission_band_renders_in_both_locales(client):
    pt = client.get("/").data.decode("utf-8")
    en = client.get("/?lang=en").data.decode("utf-8")
    assert "finalização da sua vida" in pt
    assert "submission of your life" in en


def test_tryout_offer_states_its_terms_and_links_to_whatsapp(client):
    # The free-trial claim has a loan agreement behind it. Both halves have to
    # be on the page — an offer this good with no terms beside it is the kind
    # of thing Procon reads as an ad, not a contract.
    pt = client.get("/").data.decode("utf-8")
    assert "30 dias" in pt and "comodato" in pt
    assert "wa_msg_trial" not in pt  # the key resolved, not leaked verbatim
    assert "NO%20FLAGRA" in pt  # trial message reached the wa.me link

    en = client.get("/?lang=en").data.decode("utf-8")
    assert "30 days" in en and "loan agreement" in en


def test_referral_offer_names_the_reward_in_both_locales(client):
    pt = client.get("/").data.decode("utf-8")
    en = client.get("/?lang=en").data.decode("utf-8")
    assert "um mês grátis" in pt
    assert "one month free" in en


# ---- about, legal, robots, sitemap ----


def test_about_page_renders_in_both_locales(client):
    assert "cansou de perder" in client.get("/sobre").data.decode("utf-8")
    assert "tired of missing" in client.get("/sobre?lang=en").data.decode("utf-8")


def test_privacy_page_covers_controller_and_operator_roles(client):
    body = client.get("/privacidade").data.decode("utf-8")
    assert "LGPD" in body
    assert "controladora" in body and "operador" in body


def test_terms_page_renders(client):
    assert "Termos de Uso" in client.get("/termos").data.decode("utf-8")


def test_legal_pages_are_marked_as_draft(client):
    # These are written from observed behaviour, not by a lawyer — the page
    # has to say so out loud.
    for path in ("/privacidade", "/termos"):
        assert "revis" in client.get(path).data.decode("utf-8")


def test_english_aliases_redirect_to_the_canonical_path(client):
    for alias, target in (("/about", "/sobre"),
                          ("/privacy", "/privacidade"),
                          ("/terms", "/termos")):
        resp = client.get(alias)
        assert resp.status_code == 301
        assert resp.headers["Location"].endswith(target)


def test_robots_points_at_the_sitemap_and_hides_the_app(client):
    body = client.get("/robots.txt").data.decode("utf-8")
    assert "Sitemap: https://" in body
    assert "Disallow: /app/" in body


def test_sitemap_lists_the_public_pages_with_hreflang(client):
    body = client.get("/sitemap.xml").data.decode("utf-8")
    for path in ("/", "/sobre", "/privacidade", "/termos"):
        assert f"<loc>https://noflagra.onrender.com{path}</loc>" in body
    assert 'hreflang="pt-BR"' in body and 'hreflang="en"' in body


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


# ---- device API (Phase 2) ----


def issue_pairing_code(app, gym_name=None):
    """Mint a pairing code the way scripts/create_pairing_code.py does."""
    from app.models import (
        PAIRING_CODE_LIFETIME,
        Device,
        generate_pairing_code,
        hash_pairing_code,
    )

    with app.app_context():
        establishment = (
            Establishment.query.filter_by(name=gym_name).first()
            if gym_name
            else Establishment.query.first()
        )
        device = Device(establishment_id=establishment.id, name="Gym Pi")
        code = generate_pairing_code()
        device.pairing_code_hash = hash_pairing_code(code)
        device.pairing_code_expires_at = datetime.now(timezone.utc) + PAIRING_CODE_LIFETIME
        device.pairing_status = "pending"
        _db.session.add(device)
        _db.session.commit()
        return code


def pair(client, code, cameras=("mat_camera",)):
    return client.post(
        "/api/devices/pair",
        json={"code": code, "camera_names": list(cameras)},
    )


def auth_header(uuid, key):
    return {"Authorization": f"Device {uuid}:{key}"}


def clip_payload(**overrides):
    body = {
        "camera_name": "mat_camera",
        "pressed_at": "2026-08-02T19:42:00Z",
        "start_ts": "2026-08-02T19:32:00Z",
        "end_ts": "2026-08-02T19:42:15Z",
        "duration_seconds": 615,
        "size_bytes": 184320000,
        "local_filename": "mat_2026-08-02_19-42-00.mp4",
    }
    body.update(overrides)
    return body


def test_device_pairs_and_gets_a_key_and_cameras(client, app):
    signup(client)
    code = issue_pairing_code(app)

    resp = pair(client, code, cameras=("mat_camera", "cage camera"))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["device_key"]
    assert body["establishment"] == "Yuri's BJJ"
    assert [c["name"] for c in body["cameras"]] == ["mat_camera", "cage camera"]
    # slug is what ends up in the S3 path, so it must be url-safe
    assert [c["slug"] for c in body["cameras"]] == ["mat-camera", "cage-camera"]

    from app.models import Device, hash_device_key

    with app.app_context():
        device = Device.query.filter_by(uuid=body["device_uuid"]).one()
        assert device.pairing_status == "paired"
        # the key is stored hashed, never in the clear
        assert device.device_key_hash == hash_device_key(body["device_key"])
        assert device.device_key_hash != body["device_key"]
        # the code is single use — burned on success
        assert device.pairing_code_hash is None


def test_pairing_code_cannot_be_reused(client, app):
    signup(client)
    code = issue_pairing_code(app)
    assert pair(client, code).status_code == 201
    assert pair(client, code).status_code == 401


def test_pairing_rejects_a_wrong_code(client, app):
    signup(client)
    issue_pairing_code(app)
    assert pair(client, "NOTAREALCODE").status_code == 401


def test_pairing_rejects_an_expired_code(client, app):
    signup(client)
    from app.models import Device, generate_pairing_code, hash_pairing_code

    code = generate_pairing_code()
    with app.app_context():
        establishment = Establishment.query.first()
        _db.session.add(
            Device(
                establishment_id=establishment.id,
                name="Gym Pi",
                pairing_status="pending",
                pairing_code_hash=hash_pairing_code(code),
                pairing_code_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        _db.session.commit()

    assert pair(client, code).status_code == 401


def test_pairing_rejects_duplicate_camera_names(client, app):
    signup(client)
    code = issue_pairing_code(app)
    # differ only by case/spacing, but collapse to the same slug
    resp = pair(client, code, cameras=("mat camera", "Mat_Camera"))
    assert resp.status_code == 400


def test_pairing_requires_at_least_one_camera(client, app):
    signup(client)
    code = issue_pairing_code(app)
    assert client.post("/api/devices/pair", json={"code": code, "camera_names": []}).status_code == 400


def test_clip_is_recorded_against_the_right_camera_and_tenant(client, app):
    signup(client)
    paired = pair(client, issue_pairing_code(app)).get_json()

    resp = client.post(
        "/api/clips",
        json=clip_payload(),
        headers=auth_header(paired["device_uuid"], paired["device_key"]),
    )
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "pending"

    from app.models import Clip, Device

    with app.app_context():
        clip = Clip.query.one()
        device = Device.query.one()
        establishment = Establishment.query.one()
        assert clip.establishment_id == establishment.id
        assert clip.camera_id == paired["cameras"][0]["id"]
        assert clip.duration_seconds == 615
        assert clip.local_filename == "mat_2026-08-02_19-42-00.mp4"
        # Phase 2 records metadata only; the upload is Phase 3
        assert clip.s3_key is None
        # posting a clip is also the device's heartbeat
        assert device.last_seen_at is not None


def test_clip_requires_a_valid_device_key(client, app):
    signup(client)
    paired = pair(client, issue_pairing_code(app)).get_json()

    for headers in (
        {},
        {"Authorization": "Bearer somekey"},
        auth_header(paired["device_uuid"], "wrong-key"),
        auth_header("00000000-0000-0000-0000-000000000000", paired["device_key"]),
    ):
        resp = client.post("/api/clips", json=clip_payload(), headers=headers)
        assert resp.status_code == 401, headers

    from app.models import Clip

    with app.app_context():
        assert Clip.query.count() == 0


def test_device_cannot_post_a_clip_for_another_gyms_camera(client, app):
    signup(client)
    gym_a = pair(client, issue_pairing_code(app)).get_json()

    client.post("/logout")
    signup(client, email="b@example.com", gym_name="Gym B", name="B")
    gym_b = pair(client, issue_pairing_code(app, gym_name="Gym B")).get_json()

    # Mixing one gym's UUID with the other's key must not authenticate.
    resp = client.post(
        "/api/clips",
        json=clip_payload(camera_name="mat_camera"),
        headers=auth_header(gym_a["device_uuid"], gym_b["device_key"]),
    )
    assert resp.status_code == 401

    # And a valid Gym B device may only write clips for Gym B.
    ok = client.post(
        "/api/clips",
        json=clip_payload(),
        headers=auth_header(gym_b["device_uuid"], gym_b["device_key"]),
    )
    assert ok.status_code == 201

    from app.models import Clip, Establishment as E

    with app.app_context():
        gym_b_row = E.query.filter_by(name="Gym B").one()
        clip = Clip.query.one()
        assert clip.establishment_id == gym_b_row.id


def test_clip_rejects_an_unknown_camera(client, app):
    signup(client)
    paired = pair(client, issue_pairing_code(app)).get_json()
    resp = client.post(
        "/api/clips",
        json=clip_payload(camera_name="no_such_camera"),
        headers=auth_header(paired["device_uuid"], paired["device_key"]),
    )
    assert resp.status_code == 404


def test_clip_validates_its_payload(client, app):
    signup(client)
    paired = pair(client, issue_pairing_code(app)).get_json()
    headers = auth_header(paired["device_uuid"], paired["device_key"])

    bad = [
        clip_payload(pressed_at="not-a-timestamp"),
        clip_payload(end_ts="2026-08-02T19:00:00Z"),  # before start_ts
        clip_payload(duration_seconds=-1),
        clip_payload(size_bytes="big"),
        clip_payload(camera_name=""),
    ]
    for payload in bad:
        resp = client.post("/api/clips", json=payload, headers=headers)
        assert resp.status_code == 400, payload

    from app.models import Clip

    with app.app_context():
        assert Clip.query.count() == 0


# ---- upload + sharing (Phase 3) -------------------------------------------
#
# These run against a fake object store rather than R2 itself: what's worth
# testing here is our handshake and our tenancy rules, not botocore's ability
# to sign a URL. scripts/mock_r2.py covers the real bytes-on-the-wire path.

@pytest.fixture
def storage_stub(monkeypatch):
    """A stand-in bucket: a dict of key -> size."""
    from app import storage

    objects = {}
    monkeypatch.setattr(storage, "is_configured", lambda: True)
    monkeypatch.setattr(storage, "bucket", lambda: "test-bucket")
    monkeypatch.setattr(
        storage, "presign_put",
        lambda key, content_type="video/mp4": f"https://stub.invalid/{key}?sig=put",
    )
    monkeypatch.setattr(
        storage, "presign_get",
        lambda key, download_as=None: f"https://stub.invalid/{key}?sig=get"
        + ("&dl=1" if download_as else ""),
    )
    monkeypatch.setattr(storage, "head", lambda key: objects.get(key))
    return objects


def register_clip(client, headers, **overrides):
    resp = client.post("/api/clips", json=clip_payload(**overrides), headers=headers)
    assert resp.status_code in (200, 201), resp.get_json()
    return resp.get_json()["clip_id"]


def paired_device(client, app):
    """A signed-up gym with a paired Pi — the state every upload test starts in."""
    signup(client)
    body = pair(client, issue_pairing_code(app)).get_json()
    return auth_header(body["device_uuid"], body["device_key"])


def test_registering_the_same_clip_twice_does_not_duplicate(client, app):
    headers = paired_device(client, app)
    first = client.post("/api/clips", json=clip_payload(), headers=headers)
    second = client.post("/api/clips", json=clip_payload(), headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200          # recognised as a retry
    assert first.get_json()["clip_id"] == second.get_json()["clip_id"]

    from app.models import Clip
    with app.app_context():
        assert Clip.query.count() == 1


def test_upload_url_marks_the_clip_uploading(client, app, storage_stub):
    headers = paired_device(client, app)
    clip_id = register_clip(client, headers)

    resp = client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["url"].startswith("https://stub.invalid/")
    assert body["content_type"] == "video/mp4"

    from app.models import Clip
    with app.app_context():
        clip = _db.session.get(Clip, clip_id)
        assert clip.status == "uploading"
        # the key groups by gym and camera, and carries the clip id
        assert clip.s3_key.endswith(".mp4")
        assert "/mat-camera/" in clip.s3_key
        assert f"/{clip_id}-" in clip.s3_key


def test_upload_url_is_stable_across_retries(client, app, storage_stub):
    headers = paired_device(client, app)
    clip_id = register_clip(client, headers)
    first = client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=headers)
    second = client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=headers)
    # Same key, so a retry overwrites its own object rather than orphaning one.
    assert first.get_json()["key"] == second.get_json()["key"]


def test_clip_is_only_ready_once_the_bytes_are_really_there(client, app, storage_stub):
    headers = paired_device(client, app)
    clip_id = register_clip(client, headers)
    slot = client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=headers).get_json()

    # The Pi claims success but nothing was stored: we must not believe it.
    resp = client.post(f"/api/clips/{clip_id}/uploaded", json={}, headers=headers)
    assert resp.status_code == 409
    from app.models import Clip
    with app.app_context():
        assert _db.session.get(Clip, clip_id).status == "failed"

    # Now the object exists.
    storage_stub[slot["key"]] = 12345
    resp = client.post(f"/api/clips/{clip_id}/uploaded", json={}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ready"
    assert body["size_bytes"] == 12345          # trusted from the bucket, not the Pi
    assert body["share_url"].endswith(body["share_token"])


def test_upload_can_be_reported_as_failed(client, app, storage_stub):
    headers = paired_device(client, app)
    clip_id = register_clip(client, headers)
    client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=headers)

    resp = client.post(f"/api/clips/{clip_id}/uploaded",
                       json={"failed": True, "error": "connection reset"}, headers=headers)
    assert resp.status_code == 200
    from app.models import Clip
    with app.app_context():
        clip = _db.session.get(Clip, clip_id)
        assert clip.status == "failed"
        assert "connection reset" in clip.upload_error


def test_a_device_cannot_touch_another_gyms_clip(client, app, storage_stub):
    mine = paired_device(client, app)
    clip_id = register_clip(client, mine)

    client.post("/logout")
    signup(client, email="b@example.com", gym_name="Outra Academia", name="B")
    other = pair(client, issue_pairing_code(app, gym_name="Outra Academia")).get_json()
    theirs = auth_header(other["device_uuid"], other["device_key"])

    assert client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=theirs).status_code == 404
    assert client.post(f"/api/clips/{clip_id}/uploaded", json={}, headers=theirs).status_code == 404
    assert client.get(f"/api/clips/{clip_id}", headers=theirs).status_code == 404


def test_upload_endpoints_need_a_device_key(client, app, storage_stub):
    headers = paired_device(client, app)
    clip_id = register_clip(client, headers)
    assert client.post(f"/api/clips/{clip_id}/upload-url", json={}).status_code == 401
    assert client.post(f"/api/clips/{clip_id}/uploaded", json={}).status_code == 401


def test_upload_url_says_so_when_storage_is_unconfigured(client, app, monkeypatch):
    from app import storage
    monkeypatch.setattr(storage, "is_configured", lambda: False)
    headers = paired_device(client, app)
    clip_id = register_clip(client, headers)
    resp = client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=headers)
    assert resp.status_code == 503
    assert "not configured" in resp.get_json()["error"]


def share_a_clip(client, app, storage_stub):
    headers = paired_device(client, app)
    clip_id = register_clip(client, headers)
    slot = client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=headers).get_json()
    storage_stub[slot["key"]] = 999
    body = client.post(f"/api/clips/{clip_id}/uploaded", json={}, headers=headers).get_json()
    return body["share_token"]


def test_share_page_plays_without_a_login(client, app, storage_stub):
    token = share_a_clip(client, app, storage_stub)
    resp = client.get(f"/c/{token}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert f"/c/{token}/video" in body
    # a 300 MB original must not auto-download on someone's mobile data
    assert 'preload="metadata"' in body
    # a shared clip is not something we want indexed
    assert "noindex" in body


def test_share_video_redirects_to_short_lived_storage(client, app, storage_stub):
    token = share_a_clip(client, app, storage_stub)
    resp = client.get(f"/c/{token}/video")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("https://stub.invalid/")

    download = client.get(f"/c/{token}/video?dl=1")
    assert "dl=1" in download.headers["Location"]


def test_unknown_or_unshared_tokens_are_404(client, app, storage_stub):
    assert client.get("/c/definitely-not-a-token").status_code == 404
    assert client.get("/c/definitely-not-a-token/video").status_code == 404

    # a clip that exists but was never uploaded has no token, and the row it
    # belongs to must not be reachable by guessing
    headers = paired_device(client, app)
    register_clip(client, headers)
    from app.models import Clip
    with app.app_context():
        assert Clip.query.first().share_token is None


def test_share_tokens_are_not_guessable_from_the_id(client, app, storage_stub):
    token = share_a_clip(client, app, storage_stub)
    assert len(token) >= 20
    assert token not in ("1", "2")


def test_an_empty_object_is_not_a_successful_upload(client, app, storage_stub):
    """A truncated or aborted PUT leaves a 0-byte object behind. Publishing a
    share link to that would give someone a video that plays nothing."""
    headers = paired_device(client, app)
    clip_id = register_clip(client, headers)
    slot = client.post(f"/api/clips/{clip_id}/upload-url", json={}, headers=headers).get_json()

    storage_stub[slot["key"]] = 0
    resp = client.post(f"/api/clips/{clip_id}/uploaded", json={}, headers=headers)
    assert resp.status_code == 409

    from app.models import Clip
    with app.app_context():
        clip = _db.session.get(Clip, clip_id)
        assert clip.status == "failed"
        assert clip.upload_error == "the object is empty"
        assert clip.share_token is None      # nothing public was minted
