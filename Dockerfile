# image-movie 個人デプロイ用イメージ（フロント静的ビルド + FastAPI を1コンテナに集約）
#
# ローカル確認:  docker build -t image-movie . && docker run -p 8080:8080 \
#   -e IMAGE_MOVIE_BASIC_AUTH_USER=me -e IMAGE_MOVIE_BASIC_AUTH_PASSWORD=secret image-movie
# デプロイ手順: docs/DEPLOY.md

# ---- Stage 1: フロントエンドの静的ビルド ----
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# 空文字 = 同一オリジン（FastAPI が同じホストで API を提供する）
ENV NEXT_PUBLIC_API_BASE_URL=""
RUN npm run build   # output: "export" により /fe/out に静的サイトを生成

# ---- Stage 2: ランタイム ----
FROM python:3.12-slim
# opencv-python-headless の実行に必要
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/assets ./assets
# -e: /app のソースをそのまま使う（assets/static の相対配置を保つ）
RUN pip install --no-cache-dir -e .

COPY --from=frontend /fe/out ./static

ENV PORT=8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
