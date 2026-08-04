"""
Tests for the receiver. No camera, no Frigate, no ESP32 required.

    pip install -r requirements.txt pytest
    pytest -v
"""

import time
from unittest.mock import patch

import pytest

import app as receiver


def use(**kwargs):
    """Set runtime settings directly.

    The clip window is no longer module constants — it lives in the settings
    dict the manage page edits, with the env vars as defaults. Tests poke the
    dict rather than going through save_settings(), which would try to write
    to DATA_DIR.
    """
    receiver._settings.update(kwargs)


@pytest.fixture
def client():
    receiver.app.config["TESTING"] = True
    receiver._last_trigger = 0.0
    receiver._recent.clear()
    use(post_roll_seconds=0,   # don't make the tests wait
        cooldown_seconds=20,
        lookback_seconds=600)
    receiver.SHARED_SECRET = "test-secret"
    receiver.ADMIN_PASSWORD = "test-admin"
    receiver.DRY_RUN = True  # stray background threads must not hit the network
    # Unpaired by default, so no test accidentally reaches for the cloud.
    receiver.CLOUD_URL = ""
    receiver.DEVICE_UUID = ""
    receiver.DEVICE_KEY = ""
    # The upload worker runs for real once app.py is imported. Park it, so a
    # test that queues something decides for itself when it gets processed
    # instead of racing a thread that would try to reach the network.
    receiver.uploads.stop()
    for t in receiver._threads:
        t.join(timeout=2)
    receiver._threads.clear()
    with receiver.app.test_client() as c:
        yield c
    for t in receiver._threads:  # no thread outlives its own test
        t.join(timeout=2)
    receiver._threads.clear()


def drain():
    """Wait for pending export threads so assertions aren't racing them."""
    for t in list(receiver._threads):
        t.join(timeout=2)


def press(client, token="test-secret"):
    return client.post("/save-clip", headers={"X-Auth-Token": token})


def test_rejects_missing_token(client):
    assert client.post("/save-clip").status_code == 401


def test_rejects_wrong_token(client):
    assert press(client, token="nope").status_code == 401


def test_accepts_valid_token_and_returns_immediately(client):
    with patch.object(receiver, "export_range", return_value=(True, {})):
        started = time.time()
        resp = press(client)
        assert resp.status_code == 202
        assert time.time() - started < 1.0  # ESP32 must not be left hanging
        assert resp.get_json()["clip"].startswith("mat_")


def test_export_window_is_lookback_plus_postroll(client):
    calls = []

    def fake_export(camera, start_ts, end_ts, name):
        calls.append((camera, start_ts, end_ts, name))
        return True, {"success": True}

    use(post_roll_seconds=0)
    with patch.object(receiver, "export_range", side_effect=fake_export):
        press(client)
        drain()

    assert len(calls) == 1
    camera, start_ts, end_ts, name = calls[0]
    assert camera == receiver.CAMERA_NAME
    assert round(end_ts - start_ts) == 600
    assert name.startswith("mat_")


def test_cooldown_blocks_rapid_second_press(client):
    with patch.object(receiver, "export_range", return_value=(True, {})):
        assert press(client).status_code == 202
        second = press(client)
        assert second.status_code == 429
        assert second.get_json()["status"] == "cooldown"


def test_cooldown_expires(client):
    # A real (if tiny) window, so this tests expiry rather than "no cooldown".
    use(cooldown_seconds=0.2)
    with patch.object(receiver, "export_range", return_value=(True, {})):
        assert press(client).status_code == 202
        time.sleep(0.3)
        assert press(client).status_code == 202


def test_failed_export_is_recorded_not_crashed(client):
    with patch.object(receiver, "export_range", return_value=(False, "connection refused")):
        press(client)
        drain()
    entries = client.get("/presses").get_json()
    assert len(entries) == 1
    assert entries[0]["ok"] is False


def test_clips_endpoint_lists_newest_first(client):
    use(cooldown_seconds=0)
    with patch.object(receiver, "export_range", return_value=(True, {})):
        press(client)
        drain()
        press(client)
        drain()
    entries = client.get("/presses").get_json()
    assert len(entries) == 2
    assert entries[0]["pressed_at"] >= entries[1]["pressed_at"]


def test_health_reports_unreachable_frigate(client):
    resp = client.get("/health")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["frigate_reachable"] is False


def test_export_range_builds_correct_url():
    with patch.object(receiver.requests, "post") as mock_post:
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"success": True}
        receiver.DRY_RUN = False
        ok, _ = receiver.export_range("mat_camera", 1000, 1600, "mat_test")
        assert ok
        url = mock_post.call_args[0][0]
        assert url.endswith("/api/export/mat_camera/start/1000/end/1600")
        assert mock_post.call_args[1]["json"]["playback"] == "realtime"


# ---- dashboard + clip browsing ----

def test_dashboard_renders_with_branding(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "NO FLAGRA" in body.upper()
    assert "Save" in body


def test_clips_api_empty_when_no_exports_dir(client, tmp_path):
    receiver.EXPORTS_DIR = str(tmp_path / "does-not-exist")
    body = client.get("/api/clips").get_json()
    assert body["clips"] == [] and body["total"] == 0


def seed(tmp_path, spec):
    """spec: list of (filename, seconds_ago). Returns the dir path."""
    import os
    for name, age in spec:
        f = tmp_path / name
        f.write_bytes(b"x" * 2_000_000)
        stamp = time.time() - age
        os.utime(f, (stamp, stamp))
    return str(tmp_path)


def test_clips_api_lists_newest_first(client, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [("old.mp4", 7200), ("new.mp4", 60)])
    (tmp_path / "notes.txt").write_text("ignore me")

    body = client.get("/api/clips").get_json()
    assert [c["file"] for c in body["clips"]] == ["new.mp4", "old.mp4"]
    assert body["total"] == 2          # the .txt is not counted
    assert body["clips"][0]["size_mb"] == 1.9


def test_clip_download_serves_the_file(client, tmp_path):
    receiver.EXPORTS_DIR = str(tmp_path)
    (tmp_path / "mat_test.mp4").write_bytes(b"video-bytes")
    resp = client.get("/clips/mat_test.mp4")
    assert resp.status_code == 200
    assert resp.data == b"video-bytes"


def test_clip_path_traversal_is_blocked(client, tmp_path):
    receiver.EXPORTS_DIR = str(tmp_path)
    (tmp_path.parent / "secret.txt").write_text("nope")
    resp = client.get("/clips/../secret.txt")
    assert resp.status_code in (403, 404)


def test_live_proxy_reports_camera_down(client):
    resp = client.get("/live.jpg")
    assert resp.status_code == 503


# ---- pagination, grouping, previews ----

def test_pagination_slices_without_overlap(client, tmp_path):
    receiver.EXPORTS_DIR = seed(
        tmp_path, [(f"clip{i:02d}.mp4", i * 60) for i in range(25)]
    )
    first = client.get("/api/clips?limit=10&offset=0").get_json()
    second = client.get("/api/clips?limit=10&offset=10").get_json()
    third = client.get("/api/clips?limit=10&offset=20").get_json()

    assert len(first["clips"]) == 10 and first["has_more"] is True
    assert len(third["clips"]) == 5 and third["has_more"] is False
    assert first["total"] == 25

    names = [c["file"] for c in first["clips"] + second["clips"] + third["clips"]]
    assert len(names) == len(set(names)) == 25


def test_pagination_limit_is_capped(client, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [(f"c{i}.mp4", i) for i in range(5)])
    body = client.get("/api/clips?limit=9999").get_json()
    assert body["limit"] <= 60


def test_pagination_rejects_nonsense(client, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [("a.mp4", 10)])
    assert client.get("/api/clips?limit=abc").status_code == 400
    assert client.get("/api/clips?offset=-5").get_json()["offset"] == 0


def test_clips_are_labelled_by_day(client, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [
        ("now.mp4", 300),
        ("yesterday.mp4", 30 * 3600),
        ("lastweek.mp4", 9 * 86400),
    ])
    days = {c["file"]: c["day"] for c in client.get("/api/clips").get_json()["clips"]}
    assert days["now.mp4"] == "Today"
    assert days["lastweek.mp4"] not in ("Today", "Yesterday")
    # "yesterday.mp4" is 30h old, so it lands on Yesterday or the weekday name
    assert days["yesterday.mp4"] != "Today"


def test_every_clip_advertises_a_thumbnail_url(client, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [("mat_a.mp4", 60)])
    clip = client.get("/api/clips").get_json()["clips"][0]
    assert clip["thumb"] == "/thumbs/mat_a.mp4.jpg"


def test_thumbnail_404s_for_unknown_clip(client, tmp_path):
    receiver.EXPORTS_DIR = str(tmp_path)
    receiver.THUMBS_DIR = str(tmp_path / "thumbs")
    assert client.get("/thumbs/ghost.mp4.jpg").status_code == 404


def test_thumbnail_rejects_traversal(client, tmp_path):
    receiver.EXPORTS_DIR = str(tmp_path)
    receiver.THUMBS_DIR = str(tmp_path / "thumbs")
    assert client.get("/thumbs/..%2f..%2fapp.py.jpg").status_code == 404


def test_thumbnail_404s_when_ffmpeg_cannot_read_the_file(client, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [("broken.mp4", 60)])  # not real video
    receiver.THUMBS_DIR = str(tmp_path / "thumbs")
    with patch.object(receiver, "_make_thumb", return_value=False):
        assert client.get("/thumbs/broken.mp4.jpg").status_code == 404


# ---- duplicate suppression ----

def test_cooldown_defaults_to_thirty_seconds():
    import importlib, os
    os.environ.pop("COOLDOWN_SECONDS", None)
    fresh = importlib.reload(receiver)
    assert fresh.COOLDOWN_SECONDS == 30
    importlib.reload(receiver)


def test_simultaneous_presses_yield_exactly_one_export(client):
    """20 threads hit the endpoint at once; only one may get through."""
    import threading

    use(cooldown_seconds=30)
    exports = []
    barrier = threading.Barrier(20)
    codes = []
    codes_lock = threading.Lock()

    def fake_export(camera, start_ts, end_ts, name):
        exports.append(name)
        return True, {}

    def racer():
        barrier.wait()  # release all threads at the same instant
        with receiver.app.test_client() as c:
            r = c.post("/save-clip", headers={"X-Auth-Token": "test-secret"})
        with codes_lock:
            codes.append(r.status_code)

    with patch.object(receiver, "export_range", side_effect=fake_export):
        threads = [threading.Thread(target=racer) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        drain()

    assert codes.count(202) == 1, f"expected 1 acceptance, got {codes.count(202)}"
    assert codes.count(429) == 19
    assert len(exports) == 1, f"cooldown leaked {len(exports)} exports"


def test_rejected_duplicate_does_not_extend_the_window(client):
    """Hammering the button must not push the unlock further away."""
    use(cooldown_seconds=2)
    with patch.object(receiver, "export_range", return_value=(True, {})):
        assert press(client).status_code == 202
        first = press(client).get_json()["retry_after"]
        time.sleep(0.5)
        second = press(client).get_json()["retry_after"]
    assert second < first, "retry_after should count down, not reset"


def test_cooldown_response_states_the_window(client):
    use(cooldown_seconds=30)
    with patch.object(receiver, "export_range", return_value=(True, {})):
        press(client)
        body = press(client).get_json()
        drain()
    assert body["cooldown_seconds"] == 30
    assert 0 < body["retry_after"] <= 30


def test_health_reports_cooldown_and_block_count(client):
    use(cooldown_seconds=30)
    receiver._blocked = 0
    with patch.object(receiver, "export_range", return_value=(True, {})):
        press(client)
        press(client)
        press(client)
        drain()
    body = client.get("/health").get_json()
    assert body["cooldown_active"] is True
    assert body["duplicates_blocked"] == 2


def test_unauthorised_requests_never_start_a_cooldown(client):
    """A wrong key must not lock out the real button."""
    use(cooldown_seconds=30)
    for _ in range(5):
        assert press(client, token="wrong").status_code == 401
    with patch.object(receiver, "export_range", return_value=(True, {})):
        assert press(client).status_code == 202
        drain()


# ---- cloud registration (Phase 2) ----


def pair_receiver():
    receiver.CLOUD_URL = "https://cloud.example"
    receiver.DEVICE_UUID = "abc-123"
    receiver.DEVICE_KEY = "secret-device-key"


def test_unpaired_receiver_never_calls_the_cloud(client):
    """The gym running today isn't paired, and must keep working untouched."""
    with patch.object(receiver, "export_range", return_value=(True, {})), \
            patch.object(receiver.requests, "post") as post:
        assert press(client).status_code == 202
        drain()
    post.assert_not_called()
    assert receiver.cloud_paired() is False


def test_paired_receiver_registers_the_clip(client):
    pair_receiver()
    use(lookback_seconds=600, post_roll_seconds=0)

    with patch.object(receiver, "export_range", return_value=(True, {})), \
            patch.object(receiver.requests, "post") as post:
        post.return_value.status_code = 201
        assert press(client).status_code == 202
        drain()

    post.assert_called_once()
    url = post.call_args.args[0]
    body = post.call_args.kwargs["json"]
    headers = post.call_args.kwargs["headers"]

    assert url == "https://cloud.example/api/clips"
    assert headers["Authorization"] == "Device abc-123:secret-device-key"
    assert body["camera_name"] == receiver.CAMERA_NAME
    assert body["duration_seconds"] == 600  # lookback + post-roll(0)
    assert body["local_filename"].endswith(".mp4")
    # timestamps go up as UTC ISO 8601, which is what the cloud parses
    for field in ("pressed_at", "start_ts", "end_ts"):
        assert body[field].endswith("Z"), body[field]
    assert body["start_ts"] < body["pressed_at"] <= body["end_ts"]


def test_failed_export_is_not_registered(client):
    pair_receiver()
    with patch.object(receiver, "export_range", return_value=(False, "boom")), \
            patch.object(receiver.requests, "post") as post:
        press(client)
        drain()
    post.assert_not_called()


def test_post_clip_metadata_swallows_network_errors(client):
    """The "never raises" guarantee, tested directly.

    Asserting it through press() would pass either way: the export thread
    records into _recent *before* calling the cloud, and an exception there
    only kills that thread — the request has already returned 202.
    """
    pair_receiver()
    for boom in (
        receiver.requests.RequestException("down"),
        receiver.requests.Timeout("slow"),
        receiver.requests.ConnectionError("refused"),
    ):
        with patch.object(receiver.requests, "post", side_effect=boom):
            assert receiver.post_clip_metadata(1000.0, 400.0, 1015.0, "mat_x") is None


def test_cloud_outage_does_not_break_the_export(client):
    """A clip is already safe on local disk; the cloud is best effort."""
    pair_receiver()
    with patch.object(receiver, "export_range", return_value=(True, {})), \
            patch.object(receiver.requests, "post",
                         side_effect=receiver.requests.RequestException("down")):
        assert press(client).status_code == 202
        drain()
    # the export still happened and is still listed locally
    assert receiver._recent[-1]["ok"] is True


def test_cloud_rejection_is_logged_not_raised(client):
    pair_receiver()
    with patch.object(receiver, "export_range", return_value=(True, {})), \
            patch.object(receiver.requests, "post") as post:
        post.return_value.status_code = 401
        post.return_value.text = '{"error":"unauthorized"}'
        assert press(client).status_code == 202
        drain()
    assert receiver._recent[-1]["ok"] is True


def test_health_reports_pairing_without_leaking_the_key(client):
    pair_receiver()
    body = client.get("/health").get_json()
    assert body["cloud_paired"] is True
    assert body["device_uuid"] == "abc-123"
    assert "secret-device-key" not in str(body)


# ---- export filenames (Frigate does not use the name we pass) ----

def test_export_filename_matches_what_frigate_actually_writes():
    """Regression: we used to register "<our name>.mp4" with the cloud, but
    Frigate builds the path from the camera, the window and the export id —
    our name only becomes a display label. This is a real filename produced
    by a real export, reproduced from the API's export_id."""
    from datetime import datetime

    start = datetime(2026, 7, 23, 16, 46, 52).timestamp()
    end = datetime(2026, 7, 23, 16, 57, 7).timestamp()
    got = receiver.frigate_export_filename("mat_camera", start, end, "mat_camera_7o4jf6")
    assert got == "mat_camera_20260723_164652-20260723_165707_7o4jf6.mp4"


def test_export_filename_is_none_without_an_id():
    assert receiver.frigate_export_filename("mat_camera", 1000, 1600, None) is None


def test_cloud_registration_uses_the_real_filename(client):
    pair_receiver()
    with patch.object(receiver, "export_range",
                      return_value=(True, {"export_id": "mat_camera_ab12cd"})), \
            patch.object(receiver.requests, "post") as post:
        post.return_value.status_code = 201
        assert press(client).status_code == 202
        drain()

    sent = post.call_args[1]["json"]["local_filename"]
    assert sent.startswith("mat_camera_")
    assert sent.endswith("_ab12cd.mp4")


# ---- runtime settings ----

@pytest.fixture
def admin(client, tmp_path):
    """A client whose settings/keep files land somewhere writable."""
    receiver.DATA_DIR = str(tmp_path / "data")
    yield client


def auth(token="test-admin"):
    return {"X-Admin-Token": token}


def test_settings_are_readable_without_the_password(admin):
    body = admin.get("/api/settings").get_json()
    assert body["settings"]["lookback_seconds"] == 600
    assert body["limits"]["lookback_seconds"]["max"] == 3600


def test_settings_change_needs_the_password(admin):
    assert admin.post("/api/settings", json={"lookback_seconds": 300}).status_code == 401
    assert admin.post("/api/settings", json={"lookback_seconds": 300},
                      headers=auth("wrong")).status_code == 401


def test_settings_round_trip_and_persist(admin):
    resp = admin.post("/api/settings", json={"lookback_seconds": 300}, headers=auth())
    assert resp.status_code == 200
    assert resp.get_json()["settings"]["lookback_seconds"] == 300
    # survives a reload from disk
    assert receiver.load_settings()["lookback_seconds"] == 300


def test_settings_reject_out_of_range(admin):
    resp = admin.post("/api/settings", json={"lookback_seconds": 99999}, headers=auth())
    assert resp.status_code == 400
    assert "between" in resp.get_json()["error"]


def test_settings_reject_unknown_keys(admin):
    resp = admin.post("/api/settings", json={"delete_everything": 1}, headers=auth())
    assert resp.status_code == 400


def test_a_press_uses_the_new_lookback(admin):
    admin.post("/api/settings", json={"lookback_seconds": 120, "post_roll_seconds": 0},
               headers=auth())
    calls = []
    with patch.object(receiver, "export_range",
                      side_effect=lambda c, s, e, n: (calls.append(e - s), (True, {}))[1]):
        press(admin)
        drain()
    assert round(calls[0]) == 120


def test_bad_settings_file_falls_back_to_defaults(admin, tmp_path):
    import os
    os.makedirs(receiver.DATA_DIR, exist_ok=True)
    with open(os.path.join(receiver.DATA_DIR, "settings.json"), "w") as fh:
        fh.write("{ not json at all")
    # A corrupt file must never stop the gym recording.
    assert receiver.load_settings()["lookback_seconds"] == receiver.LOOKBACK_SECONDS


# ---- deleting and keeping clips ----

def test_delete_needs_the_password(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [("a.mp4", 60)])
    assert admin.delete("/api/clips/a.mp4").status_code == 401
    assert (tmp_path / "a.mp4").exists()


def test_delete_removes_the_file(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [("a.mp4", 60)])
    resp = admin.delete("/api/clips/a.mp4", headers=auth())
    assert resp.status_code == 200
    assert resp.get_json()["deleted"] == "a.mp4"
    assert not (tmp_path / "a.mp4").exists()


def test_delete_refuses_paths_outside_exports(admin, tmp_path):
    receiver.EXPORTS_DIR = str(tmp_path)
    victim = tmp_path.parent / "secret.mp4"
    victim.write_text("nope")
    for attempt in ("../secret.mp4", "..%2Fsecret.mp4", "sub/secret.mp4"):
        assert admin.delete(f"/api/clips/{attempt}", headers=auth()).status_code in (400, 404)
    assert victim.exists()


def test_delete_refuses_non_mp4(admin, tmp_path):
    receiver.EXPORTS_DIR = str(tmp_path)
    (tmp_path / "settings.json").write_text("{}")
    assert admin.delete("/api/clips/settings.json", headers=auth()).status_code == 400
    assert (tmp_path / "settings.json").exists()


def test_kept_clips_cannot_be_deleted(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [("a.mp4", 60)])
    assert admin.post("/api/clips/a.mp4/keep", json={"keep": True},
                      headers=auth()).status_code == 200
    assert admin.delete("/api/clips/a.mp4", headers=auth()).status_code == 409
    assert (tmp_path / "a.mp4").exists()

    admin.post("/api/clips/a.mp4/keep", json={"keep": False}, headers=auth())
    assert admin.delete("/api/clips/a.mp4", headers=auth()).status_code == 200


def test_clip_list_reports_the_keep_flag(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [("a.mp4", 60), ("b.mp4", 120)])
    admin.post("/api/clips/a.mp4/keep", json={"keep": True}, headers=auth())
    clips = {c["file"]: c["kept"] for c in admin.get("/api/clips").get_json()["clips"]}
    assert clips == {"a.mp4": True, "b.mp4": False}


# ---- storage projection ----

def test_storage_reports_disk_and_measures_the_bitrate(admin, tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    receiver.EXPORTS_DIR = seed(exports, [("a.mp4", 60)])

    recordings = tmp_path / "recordings" / "2026-07-23" / "14" / "mat_camera"
    recordings.mkdir(parents=True)
    for i in range(6):
        (recordings / f"{i:02d}.00.mp4").write_bytes(b"x" * 1_000_000)
    receiver.RECORDINGS_DIR = str(tmp_path / "recordings")
    receiver._rate_cache["at"] = 0  # bypass the cache

    body = admin.get("/api/storage").get_json()
    assert body["disk"]["total_gb"] > 0
    # 6 MB in one hour -> 144 MB/day
    assert body["rate"]["gb_per_day"] == round(6_000_000 * 24 / 1073741824, 2)
    assert body["projection"]["max_retention_days"] > 0
    assert [o["days"] for o in body["projection"]["options"]] == [1, 2, 3, 7, 14, 30]


def test_storage_says_so_when_there_is_nothing_to_measure(admin, tmp_path):
    receiver.RECORDINGS_DIR = str(tmp_path / "empty")
    receiver.EXPORTS_DIR = str(tmp_path)
    receiver._rate_cache["at"] = 0
    body = admin.get("/api/storage").get_json()
    assert body["rate"] is None
    assert "note" in body


def test_manage_page_renders(admin):
    body = admin.get("/manage").get_data(as_text=True)
    assert "Storage" in body and "Clip window" in body


# ---- uploads and sharing (Phase 3) ----

import uploader as up_mod


def test_export_name_parses_into_a_window():
    got = up_mod.parse_export_name("mat_camera_20260723_164652-20260723_165707_7o4jf6.mp4")
    assert got is not None
    camera, start, end = got
    assert camera == "mat_camera"
    assert (end - start).total_seconds() == 615


def test_export_name_rejects_rubbish():
    for bad in ("", "notaclip.mp4", "mat_camera_nope-nope_x.mp4", "../escape.mp4"):
        assert up_mod.parse_export_name(bad) is None


@pytest.fixture
def queue(tmp_path):
    """An Uploader wired to a temp dir, not started — tests drive it by hand."""
    exports = tmp_path / "exports"
    exports.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    u = up_mod.Uploader({
        "data_dir": str(data), "exports_dir": str(exports),
        "camera_name": "mat_camera", "cloud_url": "https://cloud.example",
        "device_uuid": "abc-123", "device_key": "key", "paired": True,
        "timeout": 5, "upload_timeout": 30,
    }, log=lambda m: None)
    u.exports = exports
    u.data = data
    return u


CLIP = "mat_camera_20260803_140000-20260803_141015_zz9wq1.mp4"


def make_clip(queue, name=CLIP, size=2048):
    (queue.exports / name).write_bytes(b"v" * size)
    return name


def test_queue_survives_a_restart(queue, tmp_path):
    make_clip(queue)
    queue.enqueue(CLIP)

    # a brand new Uploader over the same data dir — as if the Pi rebooted
    reborn = up_mod.Uploader(dict(queue.config), log=lambda m: None)
    assert reborn.state_for(CLIP)["status"] == "queued"


def test_an_upload_interrupted_by_a_power_cut_is_retried(queue):
    make_clip(queue)
    queue.enqueue(CLIP)
    queue._set(CLIP, status="uploading")

    reborn = up_mod.Uploader(dict(queue.config), log=lambda m: None)
    # "uploading" means nobody confirmed it landed, so it goes back in the queue
    assert reborn.state_for(CLIP)["status"] == "queued"


def test_an_unpaired_pi_fails_the_clip_permanently(queue):
    make_clip(queue)
    queue.config["paired"] = False
    queue.enqueue(CLIP)
    queue._upload_one(CLIP)
    record = queue.state_for(CLIP)
    assert record["status"] == "failed"
    assert "not paired" in record["error"]


def test_a_deleted_file_drops_out_of_the_queue(queue):
    queue.enqueue("gone.mp4")
    queue._upload_one("gone.mp4")
    assert queue.state_for("gone.mp4") is None


def test_a_full_upload_records_the_share_url(queue):
    make_clip(queue)

    calls = []

    class Resp:
        def __init__(self, code, body=None):
            self.status_code = code
            self._body = body or {}
            self.text = ""

        def json(self):
            return self._body

    def fake_post(url, **kwargs):
        calls.append(url)
        if url.endswith("/api/clips"):
            return Resp(201, {"clip_id": 7})
        if url.endswith("/upload-url"):
            return Resp(200, {"url": "https://r2.example/put", "content_type": "video/mp4"})
        if url.endswith("/uploaded"):
            return Resp(200, {"status": "ready", "share_url": "https://noflagra.app/c/tok"})
        raise AssertionError(f"unexpected POST {url}")

    with patch.object(up_mod.requests, "post", side_effect=fake_post), \
            patch.object(up_mod.requests, "put", return_value=Resp(200)):
        queue._upload_one(CLIP)

    record = queue.state_for(CLIP)
    assert record["status"] == "ready"
    assert record["share_url"] == "https://noflagra.app/c/tok"
    assert record["clip_id"] == 7
    # registered, asked for a slot, confirmed — in that order
    assert [c.rsplit("/", 1)[-1] for c in calls] == ["clips", "upload-url", "uploaded"]


def test_a_network_failure_schedules_a_retry_not_a_death(queue):
    make_clip(queue)
    with patch.object(up_mod.requests, "post",
                      side_effect=up_mod.requests.RequestException("no route")):
        queue._upload_one(CLIP)

    record = queue.state_for(CLIP)
    assert record["status"] == "retry"
    assert record["attempts"] == 1
    assert record["not_before"] > time.time()   # backing off, will come back


def test_retries_give_up_eventually(queue):
    make_clip(queue)
    with patch.object(up_mod.requests, "post",
                      side_effect=up_mod.requests.RequestException("no route")):
        for _ in range(up_mod.MAX_ATTEMPTS):
            queue._set(CLIP, not_before=0)
            queue._upload_one(CLIP)

    record = queue.state_for(CLIP)
    assert record["status"] == "failed"
    assert record["attempts"] == up_mod.MAX_ATTEMPTS


def test_a_clip_already_ready_is_not_queued_again(queue):
    make_clip(queue)
    queue._set(CLIP, status="ready", share_url="https://noflagra.app/c/tok")
    assert queue.enqueue(CLIP)["status"] == "ready"


# ---- the receiver's share endpoints ----

def test_share_needs_the_password(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [(CLIP, 60)])
    assert admin.post(f"/api/clips/{CLIP}/share").status_code == 401


def test_share_refuses_when_unpaired(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [(CLIP, 60)])
    receiver.CLOUD_URL = ""
    resp = admin.post(f"/api/clips/{CLIP}/share", headers=auth())
    assert resp.status_code == 409
    assert "not paired" in resp.get_json()["error"]


def test_share_queues_the_clip(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [(CLIP, 60)])
    pair_receiver()
    receiver.uploads.config["exports_dir"] = receiver.EXPORTS_DIR
    receiver.uploads.config["data_dir"] = str(tmp_path / "updata")

    resp = admin.post(f"/api/clips/{CLIP}/share", headers=auth())
    assert resp.status_code == 202
    assert resp.get_json()["status"] == "queued"
    assert receiver.uploads.state_for(CLIP)["status"] == "queued"
    receiver.uploads.forget(CLIP)


def test_share_rejects_a_missing_or_unsafe_file(admin, tmp_path):
    receiver.EXPORTS_DIR = str(tmp_path)
    pair_receiver()
    assert admin.post("/api/clips/nope.mp4/share", headers=auth()).status_code == 404
    assert admin.post("/api/clips/..%2Fetc.mp4/share", headers=auth()).status_code in (400, 404)


def test_clip_list_carries_the_upload_state(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [(CLIP, 60)])
    receiver.uploads._set(CLIP, status="ready", share_url="https://noflagra.app/c/tok")
    clips = admin.get("/api/clips").get_json()["clips"]
    assert clips[0]["upload"] == "ready"
    assert clips[0]["share_url"] == "https://noflagra.app/c/tok"
    receiver.uploads.forget(CLIP)


def test_deleting_a_clip_drops_it_from_the_queue(admin, tmp_path):
    receiver.EXPORTS_DIR = seed(tmp_path, [(CLIP, 60)])
    receiver.uploads._set(CLIP, status="queued")
    assert admin.delete(f"/api/clips/{CLIP}", headers=auth()).status_code == 200
    assert receiver.uploads.state_for(CLIP) is None


def test_uploads_endpoint_reports_pairing(admin):
    receiver.CLOUD_URL = ""
    assert admin.get("/api/uploads").get_json()["paired"] is False
