from fastapi.testclient import TestClient

from app import tracks as track_registry
from app.main import app

client = TestClient(app)


def test_list_tracks():
    body = client.get("/tracks").json()
    ids = [t["id"] for t in body["tracks"]]
    assert ids == [t.id for t in track_registry.TRACKS]
    for t in body["tracks"]:
        # 相対パスで返す（プロキシ配下でも安全。クライアントがベースURLを前置する）
        assert t["preview_url"] == f"/tracks/{t['id']}/preview"
        assert t["license"]


def test_preview_track_returns_audio():
    track_id = track_registry.TRACKS[0].id
    res = client.get(f"/tracks/{track_id}/preview")
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/aac"
    assert res.headers["cache-control"] == "public, max-age=86400"
    assert len(res.content) > 1000


def test_preview_unknown_track_404():
    assert client.get("/tracks/nope/preview").status_code == 404


def test_resolve_auto_is_deterministic():
    a = track_registry.resolve("auto", 3)
    b = track_registry.resolve("auto", 3)
    assert a is not None and a == b


def test_resolve_rejects_empty_and_unknown():
    # 空文字を黙って auto に落とすとクライアントの欠落バグを隠すため、明示的に None
    assert track_registry.resolve("", 3) is None
    assert track_registry.resolve("nope", 3) is None


def test_create_video_with_selected_track(png_bytes, wait_done):
    files = [
        ("images", ("a.png", png_bytes((10, 10, 200)), "image/png")),
        ("images", ("b.png", png_bytes((10, 200, 10)), "image/png")),
    ]
    res = client.post("/videos", files=files, data={"track_id": "happy"})
    assert res.status_code == 202
    status = wait_done(client, res.json()["job_id"])
    assert status["state"] == "done", status.get("error")


def test_create_video_rejects_unknown_track(png_bytes):
    files = [("images", ("a.png", png_bytes((1, 1, 1)), "image/png"))]
    res = client.post("/videos", files=files, data={"track_id": "does-not-exist"})
    assert res.status_code == 400


def test_create_video_empty_track_falls_back_to_default(png_bytes, wait_done):
    """空のフォーム値はフレームワーク層で欠落扱いになり、デフォルト（auto）が適用される。

    resolve() 自体は空文字を拒否する（test_resolve_rejects_empty_and_unknown）が、
    HTTP 層では空値はフィールド省略と区別できないことをここで明文化しておく。
    """
    files = [("images", ("a.png", png_bytes((1, 1, 1)), "image/png"))]
    res = client.post("/videos", files=files, data={"track_id": ""})
    assert res.status_code == 202
    status = wait_done(client, res.json()["job_id"])
    assert status["state"] == "done", status.get("error")


def test_create_video_fails_fast_when_audio_file_missing(png_bytes, tmp_path, monkeypatch):
    """レジストリにあるがディスクに無い音源 → 202で受理せず 500 を即返す。"""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "music_dir", tmp_path)  # 空ディレクトリを指す
    try:
        files = [("images", ("a.png", png_bytes((1, 1, 1)), "image/png"))]
        res = client.post("/videos", files=files, data={"track_id": "happy"})
        assert res.status_code == 500
        assert "音源" in res.json()["detail"]
        # プレビューも 500 ではなく 404
        assert client.get("/tracks/happy/preview").status_code == 404
    finally:
        monkeypatch.undo()
