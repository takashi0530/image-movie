# image-movie 全面刷新 — 調査結果と対応方針

> 画像をアップロードすると、各画像を順に表示する動画（BGM付き）を生成するアプリ。
> Backend: FastAPI + OpenCV + moviepy / Frontend: Next.js 13 (pages router)。

---

## 1. 調査サマリ：現状の問題点

### 🔴 致命的（そのままでは動かない）

| # | 問題 | 詳細 |
|---|------|------|
| C1 | **クローンするとサーバが起動しない** | `main.py` が `from test import main as test_main` を import。しかし `test.py` は `.gitignore` の `test*.py` で除外されており **リポジトリに存在しない** → `ModuleNotFoundError` で即クラッシュ。 |
| C2 | **二重エンコード** | `cv2.VideoWriter`(`X264`) で `only_movie.mp4` を書き出し → moviepy が `VideoFileClip` で読み直し `libx264` で `music_movie.mp4` を再エンコード。動画を**2回エンコード**しており、最も重い処理を無駄に倍化。 |
| C3 | **OpenCV の H.264 依存が不安定** | `cv2.VideoWriter_fourcc(*'X264')` は環境により H.264 エンコーダを持たず、無音で失敗・破損ファイル生成のリスク。pip 版 opencv は H.264 を同梱しないことが多い。 |

### 🟠 アーキテクチャ / パフォーマンス

| # | 問題 | 影響 |
|---|------|------|
| A1 | **リクエスト同期処理** | `/uploadfile/` のハンドラ内で動画生成を完了まで実行。数十秒〜分のブロッキング、進捗なし、タイムアウト懸念、並行リクエストで詰まる。 |
| A2 | **生成した動画がフロントに返らない** | レスポンスは `{"message": "Files processed successfully"}` のみ。ユーザーは動画を取得できない（サーバのディレクトリに置かれるだけ）。 |
| A3 | **一時ファイルが溜まり続ける** | `remove_directory()` がコメントアウト。`target_images/` 配下にリクエスト毎のディレクトリと動画が無限に蓄積 → ディスク枯渇。 |
| A4 | **中央寄せの二重処理** | `resize_without_crop()` が既に黒背景キャンバスへパディング済みなのに、`resize_and_center()` がもう一度パディング。無駄な行列確保＋潜在バグ。 |
| A5 | **相対パス依存** | `AUDIO_PATH="music/am.aac"`、`temp_dir=Path("target_images")` 等が cwd 依存。起動ディレクトリが違うと壊れる。 |
| A6 | **マジックナンバー** | fps `0.4`（=1枚2.5秒）、解像度などがハードコード。設定不可。 |

### 🟡 セキュリティ / 堅牢性

| # | 問題 |
|---|------|
| S1 | `image.filename` をそのままパス連結 → **パストラバーサル**（`../../`）の余地。 |
| S2 | アップロードの **拡張子・MIME・サイズ・枚数の検証なし**。任意ファイルを書き込み可能。 |
| S3 | 例外時に `temp_dir` が残置（クリーンアップなし）。 |
| S4 | `/test/` デバッグエンドポイント、`import pdb` の残骸が本番コードに混在。 |

### 🟡 コード品質 / 構成

| # | 問題 |
|---|------|
| Q1 | **デッドコード**：`make_movie.py` の `rename_images()`・`calculate_offsets()` は未使用。`if __name__=="__main__": main()` は引数必須の `main(temp_dir)` を引数なしで呼び破綻。 |
| Q2 | **未使用ユーティリティ**：`rotate_images.py` はどこからも呼ばれない単独 CLI。 |
| Q3 | **依存の肥大**：実際に使うのは `cv2 / numpy / moviepy / fastapi` のみ。`scikit-image, scipy, PyWavelets, tifffile, networkx, imageio` 等は未使用（おそらく過去の名残）。`requirements.txt` と `Pipfile` の opencv バージョンも不一致。 |
| Q4 | 命名の不一致：ファイルは `make_movie.py` だが import は `add_music_main`、関数も `main`。意図が読み取りにくい。 |

### 🟡 フロントエンド

| # | 問題 |
|---|------|
| F1 | **boilerplate 残骸**：`index2.tsx`・`layout.tsx`（App Router用なのに pages router プロジェクト）・`page.module.css`・`globals.css` が未使用で混在。 |
| F2 | **JS/TS 混在**：実体の `index.js` だけ JS、他は TS。型の恩恵なし。 |
| F3 | **UX 皆無**：アップロード後の進捗・結果プレビュー・ダウンロード・エラー表示が一切ない。`console.log` のみ。 |
| F4 | **API URL ベタ書き**：`http://localhost:8000` をコード内に直書き。 |
| F5 | Next.js 13.4 / React 18 と古い。`tsconfig` の `target: es5` も過剰に古い。 |

---

## 2. 全面刷新の方針

### 2.1 設計ゴール
- **1回のエンコード**で完結させ、生成を高速・確実にする。
- **非同期ジョブ + 進捗 + 成果物ダウンロード**でまともな UX にする。
- **設定の外出し**・**安全な入力処理**・**確実なクリーンアップ**。
- backend/frontend ともに責務分割し、最新スタックへ更新。

### 2.2 動画生成パイプラインの刷新（最重要）

**現状**: `cv2.VideoWriter`(X264) → moviepy 読み直し → libx264 再エンコード（2回エンコード・H.264依存）

**新方式（推奨）: ffmpeg 一発生成**
1. Python(OpenCV/Pillow) で各画像を「リサイズ＋中央寄せ＋黒背景パディング」して連番 PNG/JPEG に正規化（`0001.png …`）。
2. `ffmpeg` の image2 demuxer + 音声 loop を **1コマンドで実行**し、`libx264 + aac` で MP4 を1回だけ生成。
   - 動画はフレームから直接エンコード、音声はループして多重化、長さは動画基準。
   - H.264/AAC は ffmpeg 同梱で確実。`imageio-ffmpeg` 同梱バイナリを利用すれば外部依存も最小化。
3. moviepy への依存は削除可能（軽量化・安定化）。

> 代替案: moviepy だけで `ImageSequenceClip` + 音声ループ → 1回 `write_videofile`。ffmpeg 直叩きより遅いが実装は単純。**まず ffmpeg 案を本命**、リスクヘッジで moviepy 案を fallback として用意。

正規化処理は **A4 の二重パディングを解消**し、`resize_and_center` を1関数に統合。

### 2.3 Backend 構成（責務分割）

```
backend/
├── app/
│   ├── main.py            # FastAPI app factory・ルータ登録・CORS
│   ├── config.py          # pydantic-settings（解像度/fps/音源/CORS/上限を env で）
│   ├── api/routes.py      # POST /videos(作成・202+job_id) / GET /videos/{id}(状態) / GET /videos/{id}/download
│   ├── services/
│   │   ├── images.py      # 検証・正規化（リサイズ＋中央寄せ）
│   │   └── video.py       # ffmpeg 呼び出し・生成
│   ├── jobs.py            # BackgroundTasks ベースのジョブ管理 + 自動クリーンアップ
│   └── schemas.py         # Pydantic レスポンスモデル
├── assets/music/am.aac
├── pyproject.toml         # 依存を最小化（fastapi, uvicorn, opencv-python-headless, numpy, imageio-ffmpeg, pillow）
└── tests/
```

- **非同期化**: `POST /videos` は即 `202 + job_id` を返し、`BackgroundTasks` で生成。`GET /videos/{id}` で `queued/processing/done/error`、`download` で MP4 を `FileResponse`。
- **入力検証(S1,S2)**: 拡張子allowlist・MIME・サイズ/枚数上限、`uuid` ベースの安全なファイル名で保存（元 filename は使わない）。
- **クリーンアップ(A3,S3)**: ジョブ完了/失敗後に作業ディレクトリ削除。起動時に古い残置を掃除する TTL ロジック。
- **設定の外出し(A5,A6)**: 解像度・fps・音源・CORS 許可元・上限を `config.py`(env) に集約。パスは `Path(__file__).parent` 基準の絶対パス化。
- **デッドコード除去(Q1,Q2,S4)**: `rename_images`・`calculate_offsets`・`rotate_images.py`・`/test/`・`import pdb` を削除（回転が要件なら正規化処理にオプションとして統合）。
- **依存最小化(Q3)**: `opencv-python` → `opencv-python-headless`、scikit-image系を全削除。`requirements.txt`/`Pipfile` を `pyproject.toml` に一本化。

### 2.4 Frontend 構成（最新化）

```
frontend/
├── app/
│   ├── layout.tsx         # 単一の正しい App Router レイアウト
│   ├── page.tsx           # アップロード画面（TS化）
│   └── globals.css
├── lib/api.ts             # API クライアント（base URL は env）
├── components/UploadForm.tsx, ProgressView.tsx, ResultView.tsx
└── .env.local.example     # NEXT_PUBLIC_API_BASE_URL
```

- Next.js を最新の **App Router** に統一、**全 TS 化**（F1,F2,F5）。boilerplate(`index2.tsx`/旧`layout.tsx`/未使用css)を削除。
- **UX(F3)**: ドラッグ&ドロップ、選択プレビュー、アップロード進捗、生成中ポーリング、完成動画の `<video>` プレビュー + ダウンロードボタン、エラー表示。
- **API URL の env 化(F4)**: `NEXT_PUBLIC_API_BASE_URL`。

### 2.5 横断（DX / 品質）
- `.gitignore` 見直し（`test*.py` の全除外をやめ、テストを正規管理）。
- backend に `ruff`/`black`、最小の pytest（画像正規化・検証ロジック）。
- README を実態に合わせ更新（起動手順・env・API 仕様）。
- 任意: `docker-compose`（backend+frontend）でワンコマンド起動。

---

## 3. 進め方（フェーズ）

| Phase | 内容 | 状態 |
|-------|------|------|
| 0 | **調査・方針**（本ドキュメント） | ✅ 完了 |
| 1 | Backend コア刷新：ffmpeg 単一エンコード化・正規化統合・設定外出し・デッドコード削除 | 未着手 |
| 2 | Backend API：非同期ジョブ化・ダウンロード・検証・クリーンアップ・依存最小化 | 未着手 |
| 3 | Frontend：App Router/TS 化・UX（進捗/プレビュー/DL）・env 化 | 未着手 |
| 4 | 横断：lint/test・README・.gitignore・(任意 docker) | 未着手 |

---

## 4. 確認したい論点（実装着手前）
1. **エンコード方式**：ffmpeg 一発（推奨／高速・確実）で進めてよいか。moviepy 維持希望なら別案。
2. **API 形態**：非同期ジョブ+ダウンロード（推奨）か、まずは同期で「動画を直接レスポンス返却」する最小改修か。
3. **回転機能**：`rotate_images.py` は撤去でよいか、UI から角度指定できる機能として残すか。
4. **スコープ**：Next.js のメジャーアップデート（13→最新）まで含めてよいか、13 のままで App Router 化に留めるか。
