"""
Tests for the receiver. No camera, no Frigate, no ESP32 required.

    pip install -r requirements.txt pytest
    pytest -v
"""

import time
from unittest.mock import patch

import pytest

import app as receiver


@pytest.fixture
def client():
    receiver.app.config["TESTING"] = True
    receiver._last_trigger = 0.0
    receiver._recent.clear()
    receiver.POST_ROLL_SECONDS = 0  # don't make the tests wait
    receiver.COOLDOWN_SECONDS = 20
    receiver.LOOKBACK_SECONDS = 600
    receiver.SHARED_SECRET = "test-secret"
    receiver.DRY_RUN = True  # stray background threads must not hit the network
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

    receiver.POST_ROLL_SECONDS = 0
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
    receiver.COOLDOWN_SECONDS = 0.2
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
    receiver.COOLDOWN_SECONDS = 0
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
    assert "GYM REC" in body.upper()
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

    receiver.COOLDOWN_SECONDS = 30
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
    receiver.COOLDOWN_SECONDS = 2
    with patch.object(receiver, "export_range", return_value=(True, {})):
        assert press(client).status_code == 202
        first = press(client).get_json()["retry_after"]
        time.sleep(0.5)
        second = press(client).get_json()["retry_after"]
    assert second < first, "retry_after should count down, not reset"


def test_cooldown_response_states_the_window(client):
    receiver.COOLDOWN_SECONDS = 30
    with patch.object(receiver, "export_range", return_value=(True, {})):
        press(client)
        body = press(client).get_json()
        drain()
    assert body["cooldown_seconds"] == 30
    assert 0 < body["retry_after"] <= 30


def test_health_reports_cooldown_and_block_count(client):
    receiver.COOLDOWN_SECONDS = 30
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
    receiver.COOLDOWN_SECONDS = 30
    for _ in range(5):
        assert press(client, token="wrong").status_code == 401
    with patch.object(receiver, "export_range", return_value=(True, {})):
        assert press(client).status_code == 202
        drain()
