"""API 統合テスト：画像をアップロードして実際に動画が生成されることを検証する。

TestClient は BackgroundTasks をレスポンス返却後に同期実行するため、
ステータスをポーリングすれば生成完了まで確認できる。
"""
import subprocess

import cv2
import imageio_ffmpeg
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _png_bytes(color, w=500, h=300):
    arr = np.full((h, w, 3), color, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", arr)
    assert ok
    return buf.tobytes()


def _wait_done(job_id, tries=5):
    for _ in range(tries):
        status = client.get(f"/videos/{job_id}").json()
        if status["state"] in ("done", "error"):
            return status
    return status


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_create_video_end_to_end(tmp_path):
    files = [
        ("images", ("a.png", _png_bytes((20, 20, 200)), "image/png")),
        ("images", ("b.png", _png_bytes((20, 200, 20)), "image/png")),
        ("images", ("c.png", _png_bytes((200, 20, 20)), "image/png")),
    ]
    res = client.post("/videos", files=files, data={"rotation": "90"})
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    status = _wait_done(job_id)
    assert status["state"] == "done", status.get("error")
    assert status["download_url"]

    # 動画をダウンロード
    dl = client.get(f"/videos/{job_id}/download")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "video/mp4"
    out = tmp_path / "movie.mp4"
    out.write_bytes(dl.content)
    assert out.stat().st_size > 10_000  # 空でない

    # 動画として開けること・解像度・尺を検証
    cap = cv2.VideoCapture(str(out))
    assert cap.isOpened()
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    assert (width, height) == (1920, 1080)
    # 3枚 × 2.5秒 = 7.5秒。fps=30 → 約225フレーム（多少の誤差を許容）
    duration = frame_count / fps if fps else 0
    assert 6.5 <= duration <= 8.5, f"duration={duration}s frames={frame_count} fps={fps}"

    # 音声トラックが含まれること（ffmpeg のストリーム情報で確認）
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    info = subprocess.run(
        [ffmpeg, "-i", str(out)], capture_output=True, text=True
    ).stderr
    assert "Video:" in info and "h264" in info.lower()
    assert "Audio:" in info and "aac" in info.lower()


def test_rejects_unsupported_extension():
    files = [("images", ("a.gif", b"GIF89a", "image/gif"))]
    res = client.post("/videos", files=files)
    assert res.status_code == 400


def test_rejects_invalid_rotation():
    files = [("images", ("a.png", _png_bytes((1, 1, 1)), "image/png"))]
    res = client.post("/videos", files=files, data={"rotation": "45"})
    assert res.status_code == 400


def test_status_404_for_unknown_job():
    assert client.get("/videos/does-not-exist").status_code == 404
