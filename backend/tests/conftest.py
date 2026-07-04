"""テスト共通ヘルパー。"""
import cv2
import numpy as np
import pytest


@pytest.fixture
def png_bytes():
    """指定色の PNG バイト列を返すヘルパー。"""

    def _png_bytes(color, w=500, h=300):
        arr = np.full((h, w, 3), color, dtype=np.uint8)
        ok, buf = cv2.imencode(".png", arr)
        assert ok
        return buf.tobytes()

    return _png_bytes


@pytest.fixture
def wait_done():
    """ジョブが終端状態（done/error）になるまでポーリングするヘルパー。

    TestClient は BackgroundTasks をレスポンス返却後に同期実行するため、
    通常は 1 回目のポーリングで終端に達する。
    """

    def _wait_done(client, job_id, tries=5):
        status = None
        for _ in range(tries):
            status = client.get(f"/videos/{job_id}").json()
            if status["state"] in ("done", "error"):
                break
        return status

    return _wait_done
