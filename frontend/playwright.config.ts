import { defineConfig } from "@playwright/test";

/**
 * e2e（フロント↔バックの結合）テスト設定。
 * backend（uvicorn）と frontend（next dev）を専用ポートで同時に起動し、実ブラウザで検証する。
 *
 * 前提: backend/.venv にバックエンド依存がインストール済みであること
 *   cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
 *
 * 既存の開発サーバ（例: 他プロジェクトが :3000 を使用）と衝突しないよう、
 * 専用ポートを使い reuseExistingServer は無効化している。
 */
const FRONTEND_PORT = 3210;
const BACKEND_PORT = 8123;
const API_BASE = `http://localhost:${BACKEND_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  fullyParallel: false,
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `../backend/.venv/bin/python -m uvicorn app.main:app --app-dir ../backend --port ${BACKEND_PORT}`,
      url: `${API_BASE}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        IMAGE_MOVIE_CORS_ORIGINS: `["http://localhost:${FRONTEND_PORT}"]`,
      },
    },
    {
      command: `npm run dev -- --port ${FRONTEND_PORT}`,
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: API_BASE,
      },
    },
  ],
});
