# image-movie

画像をアップロードすると、各画像を順番に表示する **BGM 付きスライドショー動画（MP4）** を生成する Web アプリ。

- **Backend**: FastAPI + OpenCV + ffmpeg（`imageio-ffmpeg` 同梱バイナリ）。非同期ジョブで動画生成。
- **Frontend**: Next.js 15（App Router / TypeScript）。アップロード〜進捗〜プレビュー〜ダウンロード。

```
.
├── backend/   # FastAPI（app/ 配下に責務分割）
├── frontend/  # Next.js (App Router)
└── docs/      # 設計・リファクタ方針
```

## アーキテクチャ

1. フロントが画像を `POST /videos` にアップロード → バックエンドは即 `202 + job_id` を返す。
2. バックグラウンドで各画像を正規化（リサイズ＋中央寄せ＋黒背景パディング＋任意回転）し、
   **ffmpeg で 1 回だけエンコード**して MP4 を生成。
3. フロントは `GET /videos/{job_id}` をポーリングし、完了したら
   `GET /videos/{job_id}/download` の動画をプレビュー＆ダウンロード。

## セットアップ

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload   # http://localhost:8000
```

- API ドキュメント: http://localhost:8000/docs
- 設定は環境変数 `IMAGE_MOVIE_*` で上書き可能（`backend/.env.example` 参照）。
- テスト: `pytest`

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # 必要なら API URL を変更
npm run dev                        # http://localhost:3000
```

詳細な設計判断・リファクタ方針は [`docs/REFACTOR_PLAN.md`](docs/REFACTOR_PLAN.md) を参照。
