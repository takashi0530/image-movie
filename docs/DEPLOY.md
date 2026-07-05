# 個人デプロイ手順（Cloud Run・実質¥0・自分だけアクセス可）

フロント（Next.js 静的ビルド）とバックエンド（FastAPI + ffmpeg）を **1つの Cloud Run サービス**に
まとめてデプロイする。全リクエストは **Basic 認証**で保護され、URL を知られても
ユーザー名/パスワードなしにはアクセスできない。通信は `*.run.app` の HTTPS で自動的に暗号化される。

## 構成

```
ブラウザ(PC/スマホ) ──HTTPS──▶ Cloud Run 1サービス（Basic認証）
                                ├─ FastAPI API（/videos /tracks /health）
                                └─ 同オリジンで Next.js 静的ビルドを配信（CORS不要）
```

- min-instances=0（アイドル時は完全停止＝課金ゼロ、初回アクセスに数秒のコールドスタート）
- max-instances=1（インメモリのジョブ管理と整合。個人利用では性能も十分）

## 事前準備（初回のみ）

```bash
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

## デプロイ

リポジトリのルートで:

```bash
gcloud run deploy image-movie \
  --source . \
  --region asia-northeast1 \
  --memory 2Gi --cpu 1 \
  --min-instances 0 --max-instances 1 \
  --timeout 300 \
  --no-cpu-throttling \
  --execution-environment gen2 \
  --allow-unauthenticated \
  --set-env-vars "IMAGE_MOVIE_BASIC_AUTH_USER=<好きなユーザー名>,IMAGE_MOVIE_BASIC_AUTH_PASSWORD=<長いランダムなパスワード>"
```

重要なフラグの理由:
- **`--no-cpu-throttling`（必須）**: 動画生成はレスポンス返却後のバックグラウンドで走る。
  既定（リクエスト課金）ではリクエスト処理外の CPU がほぼ止められ、エンコードが
  進まない/インスタンス回収でジョブ消失が起きる。このフラグでインスタンス稼働中は
  常時 CPU が割り当てられる（課金はインスタンス稼働時間ベースになるが、
  min-instances=0 なら最後のリクエスト後 ~15分でゼロに戻り、個人利用は無料枠内）。
- **`--memory 2Gi`**: Cloud Run の書込FSは RAM 共有（tmpfs）。画像デコード + ffmpeg +
  一時ファイルのピークを考慮すると 1Gi は余裕がなく、2Gi が安全（無料枠内で収まる）。
- **`--execution-environment gen2`**: ローカル Docker 検証と同じ完全な Linux 環境で
  ffmpeg/opencv を動かす（gen1 の gVisor 互換層による稀な差異を回避）。

- `--allow-unauthenticated` は「Cloud Run の IAM 層を通す」という意味で、
  実際のアクセスはアプリ側の Basic 認証がブロックする。
- パスワードは `openssl rand -base64 24` などで生成した長いものを使うこと。
- 表示された `https://image-movie-xxxx.run.app` にアクセス → Basic 認証ダイアログ → 利用開始。
  スマホはこの URL をホーム画面に追加すると便利。

### パスワードを Secret Manager で管理する場合（推奨・任意）

```bash
echo -n "<パスワード>" | gcloud secrets create image-movie-basic-pass --data-file=-
gcloud run deploy image-movie \
  --source . --region asia-northeast1 \
  --memory 2Gi --min-instances 0 --max-instances 1 --timeout 300 \
  --no-cpu-throttling --execution-environment gen2 \
  --allow-unauthenticated \
  --set-env-vars "IMAGE_MOVIE_BASIC_AUTH_USER=<ユーザー名>" \
  --set-secrets "IMAGE_MOVIE_BASIC_AUTH_PASSWORD=image-movie-basic-pass:latest"
```

※ アプリは片方の環境変数だけ設定された状態では起動しません（fail-closed。
   誤設定のまま認証なしで公開されるのを防ぐため）。

※ Secret Manager 登録時は末尾に改行を入れないこと（`echo -n` を使う）。

## より強固にしたい場合（代替）

Basic 認証の代わりに Cloud Run の IAM 認証だけで守る方法もある:
`--no-allow-unauthenticated` でデプロイし、`gcloud run services proxy` 経由でアクセスする。
最も堅牢だが、スマホのブラウザから直接開けなくなるため、個人利用の利便性では Basic 認証を推奨。

## 制約・メモ

- **1リクエストの上限は約32MB**（Cloud Run の HTTP/1 制限）。フロント側で合計30MBを
  超える選択は送信前にブロックする。超える場合は分割するか、将来的に GCS 署名付き URL
  直アップロードへ移行する（docs/INFRA_DESIGN.md §2 参照）。
- 生成した動画はコンテナ内 `/tmp` 相当（インスタンス内）に置かれ、TTL(1時間) または
  インスタンス停止で消える。**必要な動画はすぐダウンロードする**こと。
- **生成中はタブを開いたままにする**。ポーリングが止まって無トラフィックになると、
  アイドル判定でインスタンスが回収され、処理中ジョブは消える（ジョブ管理はインメモリ）。
  再訪時に「ジョブが見つかりません(404)」となるのはインスタンス再起動が理由。
- コスト: Cloud Run 無料枠（月18万 vCPU秒等）に対し、個人利用（月数十本）は余裕で収まる。
  下り転送のみ大量 DL 時に微課金の可能性（docs/INFRA_DESIGN.md §11 参照）。

## ローカルで本番相当を確認する

```bash
# フロントを静的ビルドして FastAPI に配信させる
cd frontend && NEXT_PUBLIC_API_BASE_URL="" npm run build && cp -r out ../backend/static
cd ../backend && IMAGE_MOVIE_BASIC_AUTH_USER=me IMAGE_MOVIE_BASIC_AUTH_PASSWORD=secret \
  .venv/bin/uvicorn app.main:app --port 8080
# → http://localhost:8080 （Basic認証: me / secret）
```
