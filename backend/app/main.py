"""FastAPI アプリケーションのエントリーポイント。

起動: `uvicorn app.main:app --reload`（backend/ ディレクトリで実行）
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import get_settings
from .jobs import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時に古いジョブの残置を掃除
    settings = get_settings()
    store.cleanup_expired(settings.job_ttl_seconds)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="image-movie API", version="1.0.0", lifespan=lifespan)
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

    return app


app = create_app()
