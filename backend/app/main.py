"""FastAPI アプリケーションのエントリーポイント。

起動: `uvicorn app.main:app --reload`（backend/ ディレクトリで実行）

本番（個人デプロイ）では 1 サービスに集約する:
- IMAGE_MOVIE_BASIC_AUTH_USER / _PASSWORD を設定すると全リクエストを Basic 認証で保護
- static_dir（フロントの next build 出力）が存在すれば同一オリジンで配信（CORS 不要）
"""
from __future__ import annotations

import base64
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from .api.routes import router
from .config import get_settings
from .jobs import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時に古いジョブの残置を掃除
    settings = get_settings()
    store.cleanup_expired(settings.job_ttl_seconds)
    yield


def _basic_auth_middleware(user: str, password: str):
    """全リクエストを Basic 認証で保護するミドルウェアを返す。"""
    expected = base64.b64encode(f"{user}:{password}".encode()).decode()

    async def middleware(request: Request, call_next):
        auth = request.headers.get("Authorization", "")
        ok = auth.startswith("Basic ") and secrets.compare_digest(
            auth[len("Basic "):], expected
        )
        if not ok:
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="image-movie"'},
            )
        return await call_next(request)

    return middleware


def create_app() -> FastAPI:
    # ジョブ処理時間などのアプリログを INFO で出す（uvicorn のログと共存）
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    settings = get_settings()
    app = FastAPI(title="image-movie API", version="1.0.0", lifespan=lifespan)

    if settings.basic_auth_user and settings.basic_auth_password:
        app.middleware("http")(
            _basic_auth_middleware(settings.basic_auth_user, settings.basic_auth_password)
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    # フロントの静的ビルドを同一オリジンで配信（API ルートが優先され、残りがここに落ちる）
    if settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")

    return app


app = create_app()
