"""Basic 認証ミドルウェアのテスト。"""
import base64

from fastapi.testclient import TestClient

from app.config import get_settings


def _make_app(monkeypatch, user: str, password: str):
    monkeypatch.setenv("IMAGE_MOVIE_BASIC_AUTH_USER", user)
    monkeypatch.setenv("IMAGE_MOVIE_BASIC_AUTH_PASSWORD", password)
    get_settings.cache_clear()
    from app.main import create_app

    return create_app()


def _cleanup():
    get_settings.cache_clear()


def _basic(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_basic_auth_blocks_without_credentials(monkeypatch):
    try:
        client = TestClient(_make_app(monkeypatch, "me", "secret"))
        res = client.get("/health")
        assert res.status_code == 401
        assert res.headers["WWW-Authenticate"].startswith("Basic")
        # API も同様に保護される
        assert client.get("/tracks").status_code == 401
    finally:
        _cleanup()


def test_basic_auth_allows_correct_credentials(monkeypatch):
    try:
        client = TestClient(_make_app(monkeypatch, "me", "secret"))
        assert client.get("/health", headers=_basic("me", "secret")).status_code == 200
        assert client.get("/tracks", headers=_basic("me", "secret")).status_code == 200
    finally:
        _cleanup()


def test_basic_auth_rejects_wrong_password(monkeypatch):
    try:
        client = TestClient(_make_app(monkeypatch, "me", "secret"))
        assert client.get("/health", headers=_basic("me", "WRONG")).status_code == 401
    finally:
        _cleanup()


def test_malformed_non_ascii_header_is_401_not_500(monkeypatch):
    """非ASCIIの Authorization ヘッダで 500 にならず 401 を返す。"""
    try:
        client = TestClient(_make_app(monkeypatch, "me", "secret"))
        res = client.get(
            "/health", headers={b"Authorization": b"Basic \xff\xff\xff\xff"}
        )
        assert res.status_code == 401
    finally:
        _cleanup()


def test_partial_auth_config_fails_closed(monkeypatch):
    """片方の環境変数だけ設定された場合は起動を拒否する（認証なし公開の防止）。"""
    import pytest

    monkeypatch.setenv("IMAGE_MOVIE_BASIC_AUTH_USER", "me")
    monkeypatch.delenv("IMAGE_MOVIE_BASIC_AUTH_PASSWORD", raising=False)
    get_settings.cache_clear()
    try:
        from app.main import create_app

        with pytest.raises(RuntimeError):
            create_app()
    finally:
        _cleanup()


def test_no_auth_when_not_configured():
    # 環境変数未設定（デフォルト）の場合は認証なしで通る（ローカル開発）
    get_settings.cache_clear()
    try:
        from app.main import create_app

        client = TestClient(create_app())
        assert client.get("/health").status_code == 200
    finally:
        _cleanup()
