import cv2
import numpy as np
from fastapi.testclient import TestClient

from app import tracks as track_registry
from app.main import app

client = TestClient(app)


def _png_bytes(color, w=400, h=300):
    ok, buf = cv2.imencode(".png", np.full((h, w, 3), color, dtype=np.uint8))
    assert ok
    return buf.tobytes()


def _wait_done(job_id, tries=5):
    status = None
    for _ in range(tries):
        status = client.get(f"/videos/{job_id}").json()
        if status["state"] in ("done", "error"):
            break
    return status


def test_list_tracks():
    body = client.get("/tracks").json()
    ids = [t["id"] for t in body["tracks"]]
    assert ids == [t.id for t in track_registry.TRACKS]
    for t in body["tracks"]:
        assert t["preview_url"].endswith(f"/tracks/{t['id']}/preview")
        assert t["license"]


def test_preview_track_returns_audio():
    track_id = track_registry.TRACKS[0].id
    res = client.get(f"/tracks/{track_id}/preview")
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/aac"
    assert len(res.content) > 1000


def test_preview_unknown_track_404():
    assert client.get("/tracks/nope/preview").status_code == 404


def test_resolve_auto_is_deterministic():
    a = track_registry.resolve("auto", 3)
    b = track_registry.resolve("auto", 3)
    assert a is not None and a == b


def test_create_video_with_selected_track():
    files = [
        ("images", ("a.png", _png_bytes((10, 10, 200)), "image/png")),
        ("images", ("b.png", _png_bytes((10, 200, 10)), "image/png")),
    ]
    res = client.post("/videos", files=files, data={"track_id": "happy"})
    assert res.status_code == 202
    status = _wait_done(res.json()["job_id"])
    assert status["state"] == "done", status.get("error")


def test_create_video_rejects_unknown_track():
    files = [("images", ("a.png", _png_bytes((1, 1, 1)), "image/png"))]
    res = client.post("/videos", files=files, data={"track_id": "does-not-exist"})
    assert res.status_code == 400
