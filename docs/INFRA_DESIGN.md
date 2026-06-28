# image-movie 本番インフラ設計（詳細）

> 推奨構成：GCP マネージド（Cloud Run + Cloud Tasks + GCS + Firestore）。
> 「軽量 API」と「重いエンコード Worker」を分離し、画像/動画は **GCS へ署名付きURLで直接** 入出力する。

---

## 1. 設計原則

1. **API と エンコードを分離**：ffmpeg は CPU バウンドで時間がかかる。API スレッドをブロックさせず、キュー経由で Worker に渡す。
2. **大容量データは API を経由させない**：アップロード/ダウンロードは GCS の **署名付きURL** でクライアント ↔ ストレージ直結。API の帯域・メモリを節約。
3. **状態はマネージドに置く**：ジョブ状態・ユーザー・課金は Firestore（or Cloud SQL）。Worker/API はステートレスに保ち水平スケール可能に。
4. **使い捨て・自動削除**：入出力は GCS ライフサイクルで TTL 自動削除（プライバシー & コスト）。
5. **濫用前提で守る**：認証・レート制限・サイズ/枚数上限・コンテンツ検査・署名URLの短期失効。

---

## 2. コンテナ構成図（C4: Container レベル）

```mermaid
flowchart TB
    subgraph Client["クライアント"]
        FE["Next.js (Vercel)\n+ CDN"]
    end

    subgraph GCP["GCP プロジェクト"]
        API["API サービス\nCloud Run (軽量・常時)\n認証/署名URL発行/ジョブ作成"]
        Q["Cloud Tasks\n(ジョブキュー)"]
        W["Worker サービス\nCloud Run (CPU多め・長時間)\nffmpeg エンコード"]
        DB[("Firestore\nジョブ/ユーザー/課金")]
        subgraph Storage["Cloud Storage"]
            IN[("uploads バケット\n入力画像")]
            OUT[("outputs バケット\n生成MP4")]
        end
        SM["Secret Manager"]
        MON["Cloud Logging /\nMonitoring / Error Reporting"]
    end

    subgraph External["外部サービス"]
        AUTH["Firebase Auth /\nIdentity Platform"]
        PAY["Stripe"]
        BGM["BGMライブラリ\n(ライセンス済み音源)"]
    end

    FE -->|"1. ログイン"| AUTH
    FE -->|"2. ジョブ作成 (JWT)"| API
    API -->|署名URL発行| IN
    FE -->|"3. 画像を直接PUT"| IN
    API -->|"4. enqueue"| Q
    Q -->|"5. push"| W
    W -->|"6. 入力取得"| IN
    W -->|"7. MP4書込"| OUT
    W -->|状態更新| DB
    API -->|状態参照| DB
    FE -->|"8. ポーリング (JWT)"| API
    FE -->|"9. 署名URLでDL"| OUT
    API -->|決済/サブスク| PAY
    API --> SM
    W --> SM
    API -.->|ログ| MON
    W -.->|ログ| MON
    W -. 取得 .-> BGM
```

---

## 3. ユースケース図

```mermaid
flowchart LR
    guest(("匿名ユーザー"))
    user(("登録ユーザー"))
    paid(("課金ユーザー"))
    admin(("管理者"))

    subgraph System["image-movie"]
        UC1["画像をアップロード"]
        UC2["スライドショー動画を生成"]
        UC3["生成状況を確認"]
        UC4["動画をプレビュー/ダウンロード\n(透かしあり)"]
        UC5["HD・透かしなしで書き出し"]
        UC6["BGM/テンプレートを選択"]
        UC7["アカウント管理"]
        UC8["決済・サブスク契約"]
        UC9["利用状況/エラーを監視"]
        UC10["濫用ユーザーの制限"]
    end

    PAY(("Stripe"))
    AUTH(("Auth基盤"))

    guest --> UC1 & UC2 & UC3 & UC4
    user --> UC6 & UC7
    user --> UC1
    paid --> UC5 & UC8
    admin --> UC9 & UC10
    UC7 -.-> AUTH
    UC8 -.-> PAY
```

- 匿名でも「生成 → 透かし付きプレビュー/DL」まで可能（CV 前の体験を最大化）。
- HD・透かしなしは課金ユーザー限定。BGM/テンプレ選択は登録で開放。

---

## 4. シーケンス図

### 4.1 動画生成（ハッピーパス：署名URL直アップロード方式・推奨）

```mermaid
sequenceDiagram
    autonumber
    participant FE as Frontend
    participant AU as Auth
    participant API as API (Cloud Run)
    participant GIN as GCS uploads
    participant Q as Cloud Tasks
    participant W as Worker (Cloud Run)
    participant GOUT as GCS outputs
    participant DB as Firestore

    FE->>AU: ログイン
    AU-->>FE: ID トークン(JWT)
    FE->>API: POST /jobs (枚数・rotation, JWT)
    API->>API: 認証/レート制限/上限チェック
    API->>DB: ジョブ作成 (state=created)
    API->>GIN: 署名付きアップロードURLを発行(各画像)
    API-->>FE: job_id + 署名URL[]
    loop 各画像
        FE->>GIN: PUT 画像 (直接)
    end
    FE->>API: POST /jobs/{id}/start (JWT)
    API->>Q: enqueue(job_id)
    API->>DB: state=queued
    API-->>FE: 202 Accepted
    Q->>W: push(job_id)
    W->>DB: state=processing
    W->>GIN: 入力画像を取得
    W->>W: 正規化 + ffmpeg 単一エンコード
    W->>GOUT: movie.mp4 を書込
    W->>DB: state=done, output参照
    loop ポーリング
        FE->>API: GET /jobs/{id} (JWT)
        API->>DB: 状態取得
        API-->>FE: state / (done なら署名DL URL)
    end
    FE->>GOUT: 署名URLで動画を取得
```

> 補足：MVP では「API がアップロードを受けて自分で GCS に置く」簡易版でも可。
> ただし大量/大容量画像では API 帯域・メモリを圧迫するため、本番は署名URL直アップロードを推奨。

### 4.2 HD 書き出し（課金フロー）

```mermaid
sequenceDiagram
    autonumber
    participant FE as Frontend
    participant API as API
    participant PAY as Stripe
    participant Q as Cloud Tasks
    participant W as Worker
    participant DB as Firestore

    FE->>API: POST /jobs/{id}/export-hd (JWT)
    API->>DB: 課金状態を確認
    alt 未課金
        API->>PAY: Checkout セッション作成
        API-->>FE: 決済URL
        FE->>PAY: 決済
        PAY-->>API: Webhook (支払い完了)
        API->>DB: entitlement 付与
    end
    API->>Q: enqueue(HD レンダリング)
    Q->>W: push
    W->>W: 透かしなし・高ビットレートで再生成
    W->>DB: state=done(HD)
    API-->>FE: HD ダウンロードURL
```

### 4.3 失敗・リトライ

```mermaid
sequenceDiagram
    autonumber
    participant Q as Cloud Tasks
    participant W as Worker
    participant DB as Firestore
    participant MON as Monitoring

    Q->>W: push(job_id)
    W->>W: ffmpeg 実行
    alt 失敗(一時的)
        W->>DB: state=error(retryable)
        W-->>Q: 5xx 返却 → 自動リトライ(指数バックオフ)
    else 失敗(恒久的: 不正入力等)
        W->>DB: state=failed(理由)
        W->>MON: エラー通知
        W-->>Q: 200 (リトライさせない)
    end
```

---

## 5. 各コンポーネント詳細

| 層 | 採用 | 主設定/ポイント |
|---|---|---|
| フロント | Next.js / Vercel | 静的配信 + CDN。`NEXT_PUBLIC_API_BASE_URL` で API 切替 |
| API | Cloud Run | min-instances=0〜1、concurrency 高め。CPU 控えめ。役割：認証・署名URL発行・ジョブ管理・課金 |
| キュー | Cloud Tasks | 1ジョブ=1タスク。最大試行回数・バックオフ・ディスパッチ並列度を設定 |
| Worker | Cloud Run | CPU 2〜4・メモリ多め、timeout 長め(〜数分)、concurrency=1（1本=1コンテナで安定）。min-instances=0 でアイドル課金ゼロ |
| ストレージ | GCS (uploads/outputs) | 署名URL(短期失効)。ライフサイクルで TTL 自動削除。CMEK/暗号化はデフォルト |
| DB | Firestore | ジョブ・ユーザー・entitlement。サーバレスでスケール。複雑な集計が要れば Cloud SQL |
| 認証 | Firebase Auth | メール/Google/LINE。匿名サインインで匿名利用も追跡可 |
| 決済 | Stripe | Checkout + Webhook。entitlement を Firestore に反映 |
| シークレット | Secret Manager | Stripe鍵・BGMライセンス等。末尾改行に注意 |
| 監視 | Cloud Logging/Monitoring/Error Reporting (+Sentry) | ジョブ成功率・所要時間・キュー滞留をメトリクス化 |
| CDN/配信 | 署名URL + (必要なら Cloud CDN) | 出力動画の配信。直リンク失効で保護 |

---

## 6. スケーリングと性能

- **水平スケール**：Worker は「1コンテナ=1ジョブ(concurrency=1)」。同時生成数 = Worker インスタンス数。Cloud Run が需要に応じて自動増減。
- **1本の所要**：30枚/75秒/1080p の静止フレーム libx264 は数秒〜十数秒（CPU依存）。`-preset`/`-crf` で調整。
- **重い入力の抑制**：縦型/SNS短尺/解像度プリセットを用意し 4K を既定にしない。
- **コールドスタート対策**：体験重視なら API は min-instances=1。Worker は 0 でも可（数秒の起動許容）。
- **バックプレッシャ**：Cloud Tasks のディスパッチ上限で Worker 過負荷を防止。キュー滞留はアラート。

---

## 7. セキュリティ / コンプライアンス

- 署名URL は **短期失効 + メソッド/パス限定**。アップロードは content-type/サイズ条件付き。
- API は JWT 検証 + ユーザー単位レート制限 + 1ジョブの枚数/総サイズ上限。
- 画像のコンテンツ検査（不適切画像）— SafeSearch 等を Worker 前段に。
- 出力はデフォルト非公開バケット。配信は署名URLのみ。
- **BGM 著作権**：ライセンス済み音源のみ使用 or ユーザー持ち込み（最重要・法的ブロッカー）。
- 規約/プライバシー（アップロード画像の保持期間・削除を明記）、課金時は特商法表記。

---

## 8. コスト（marginal は極小、固定費と濫用が論点）

- 1本あたり：CPU 数秒 + ストレージ数MB + 転送0.1〜0.2円 → **数円未満**。
- 固定費：Cloud Run/Firestore 最小構成は月 0〜数千円から。BGM 商用ライセンスが最大の固定費（月 数千〜2万円規模）。
- 防御：無料枠は透かし/低画質・要ログイン・TTL削除で濫用コストを抑制。

---

## 9. 代替（最安・自前運用：VPS 構成）

```mermaid
flowchart LR
    FE2["Next.js"] --> NGINX["Nginx (TLS/逆プロキシ)"]
    NGINX --> API2["FastAPI (uvicorn/gunicorn)"]
    API2 --> REDIS[("Redis")]
    REDIS --> CELERY["Celery Worker (ffmpeg)"]
    API2 --> PG[("PostgreSQL")]
    CELERY --> OBJ[("S3互換/ローカル + TTL")]
```

- 1台の VPS に API + Redis + Celery + Postgres。固定費が安い（月 数千円〜）。
- 短所：スケール・冗長化・バックアップ・監視を自前。トラフィック増で手当てが必要。
- 位置づけ：**ごく初期の検証**。需要が見えたら GCP マネージドへ移行。

---

## 10. 現状コードからの移行ステップ

1. ジョブ状態を **インメモリ → Firestore** に置換（`app/jobs.py` の差し替え）。
2. ローカル保存 → **GCS** に置換（uploads/outputs、署名URL 発行を API に追加）。
3. `BackgroundTasks` → **Cloud Tasks + Worker（同コードを worker エントリで実行）** に分離。
4. 認証（Firebase Auth）・レート制限・上限を API に追加。
5. BGM をライセンスクリア音源へ差し替え（or 持ち込み式）。
6. 監視・規約・課金（Stripe）を整備して公開。
