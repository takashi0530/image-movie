"""リリース前ハードニングのテスト。

本番（Cloud Run 単一サービス）で実際に踏み得る経路を固定する:
静的配信×認証、TTL失効後のアクセス、破損画像のエラーパス、
未完了ジョブのダウンロード、サイズ上限の書き込み時強制、CORSプリフライト。
"""
import base64
import io
import time

import pytest
from fastapi.testclient import TestClient

from app.api.routes import save_upload_capped
from app.config import get_settings
from app.jobs import store
from app.main import app
from app.services.images import ValidationError

client = TestClient(app)


# ---------------------------------------------------------------- サイズ上限（書き込み時強制）

def test_save_upload_capped_rejects_oversize(tmp_path):
    """UploadFile.size が None（content-length なし）でも実バイト数で上限を強制する。"""
    src = io.BytesIO(b"x" * 100)
    with pytest.raises(ValidationError):
        save_upload_capped(src, tmp_path / "big.jpg", max_bytes=50)


def test_save_upload_capped_accepts_within_limit(tmp_path):
    src = io.BytesIO(b"x" * 40)
    dest = tmp_path / "ok.jpg"
    save_upload_capped(src, dest, max_bytes=50)
    assert dest.read_bytes() == b"x" * 40


# ---------------------------------------------------------------- 静的配信 × Basic認証（本番構成）

def test_static_serving_with_basic_auth(tmp_path, monkeypatch):
    """Cloud Run 本番と同じ「静的配信 + 認証」構成の統合テスト。"""
    (tmp_path / "index.html").write_text("<html>IMAGE-MOVIE-TEST</html>")
    monkeypatch.setenv("IMAGE_MOVIE_STATIC_DIR", str(tmp_path))
    monkeypatch.setenv("IMAGE_MOVIE_BASIC_AUTH_USER", "me")
    monkeypatch.setenv("IMAGE_MOVIE_BASIC_AUTH_PASSWORD", "secret")
    get_settings.cache_clear()
    try:
        from app.main import create_app

        c = TestClient(create_app())
        creds = {"Authorization": "Basic " + base64.b64encode(b"me:secret").decode()}

        # 認証なしは静的ファイルも 401
        assert c.get("/").status_code == 401
        # 認証ありで index.html が配信される
        res = c.get("/", headers=creds)
        assert res.status_code == 200
        assert "IMAGE-MOVIE-TEST" in res.text
        # API ルートが静的マウントより優先される
        assert c.get("/tracks", headers=creds).json()["tracks"]
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------- ジョブのライフサイクル

def _small_job(png_bytes) -> str:
    files = [("images", ("a.png", png_bytes((1, 1, 1)), "image/png"))]
    res = client.post("/videos", files=files)
    assert res.status_code == 202
    return res.json()["job_id"]


def test_expired_job_returns_404_not_500(png_bytes, wait_done):
    """TTL 失効でクリーンアップされたジョブへのアクセスは 404（500にしない）。"""
    job_id = _small_job(png_bytes)
    wait_done(client, job_id)

    # 作成時刻を TTL より過去に偽装し、次の POST でクリーンアップを発火させる
    job = store.get(job_id)
    work_dir = job.work_dir
    job.created_at = time.time() - get_settings().job_ttl_seconds - 10
    _small_job(png_bytes)  # cleanup_expired が走る

    assert store.get(job_id) is None
    assert not work_dir.exists()
    assert client.get(f"/videos/{job_id}").status_code == 404
    assert client.get(f"/videos/{job_id}/download").status_code == 404


def test_all_corrupt_images_yields_error_state(wait_done):
    """拡張子は正しいが中身が画像でない場合: 202 受理 → state=error → download 404。

    無限スピナー（processing のまま固まる）にならないことを保証する。
    """
    files = [
        ("images", ("a.jpg", b"this is not a jpeg", "image/jpeg")),
        ("images", ("b.jpg", b"neither is this", "image/jpeg")),
    ]
    res = client.post("/videos", files=files)
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    status = wait_done(client, job_id)
    assert status["state"] == "error"
    assert "有効な画像" in (status["error"] or "")
    assert status["download_url"] is None
    assert client.get(f"/videos/{job_id}/download").status_code == 404


def test_intermediates_freed_after_success(png_bytes, wait_done):
    """成功後は uploads/frames を即解放し movie.mp4 だけ残す（Cloud Run の RAM 圧迫防止）。"""
    job_id = _small_job(png_bytes)
    status = wait_done(client, job_id)
    assert status["state"] == "done"

    work_dir = store.get(job_id).work_dir
    assert not (work_dir / "uploads").exists()
    assert not (work_dir / "frames").exists()
    assert (work_dir / "movie.mp4").exists()
    assert client.get(f"/videos/{job_id}/download").status_code == 200


def test_download_of_unfinished_job_is_404():
    """queued/processing のジョブのダウンロードは 404（途中ファイルを返さない）。"""
    job = store.create("test-unfinished-job", get_settings().work_dir / "test-unfinished-job")
    try:
        assert client.get(f"/videos/{job.id}/download").status_code == 404
    finally:
        store._jobs.pop(job.id, None)


# ---------------------------------------------------------------- CORS プリフライト × 認証の順序

def test_cors_preflight_succeeds_without_credentials(monkeypatch):
    """ブラウザは preflight に認証ヘッダを付けない。CORSMiddleware が Basic 認証の
    外側で応答する（ミドルウェア登録順の不変条件）ことを固定する。"""
    monkeypatch.setenv("IMAGE_MOVIE_BASIC_AUTH_USER", "me")
    monkeypatch.setenv("IMAGE_MOVIE_BASIC_AUTH_PASSWORD", "secret")
    get_settings.cache_clear()
    try:
        from app.main import create_app

        c = TestClient(create_app())
        res = c.options(
            "/videos",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    finally:
        get_settings.cache_clear()
