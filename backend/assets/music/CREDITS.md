# BGM クレジット / ライセンス

同梱の BGM は **Kevin MacLeod (incompetech.com)** の楽曲です。
ライセンスは **Creative Commons: By Attribution 4.0**（CC BY 4.0）
<http://creativecommons.org/licenses/by/4.0/> — **再配布・改変可、クレジット表記必須**。

取得・整音（95秒トリム / -14LUFS 正規化 / フェードアウト / AAC 192k）は
`backend/scripts/fetch_free_tracks.py` で再現できます。

| ファイル | UI表示 | 原曲 |
|---|---|---|
| upbeat.aac | アップテンポ | "Monkeys Spinning Monkeys" |
| pop.aac | ポップ | "Carefree" |
| cafe.aac | カフェ | "Lobby Time" |
| bossa.aac | ボサノバ | "Bossa Antigua" |
| dance.aac | ダンス | "Disco con Tutti" |
| house.aac | ハウス | "Voxel Revolution" |
| electro.aac | エレクトロ | "Electrodoodle" |

## 必要なクレジット表記（CC BY 4.0）

アプリの UI には各曲のクレジットを可視表示しています。**生成した動画を公開する場合は、
動画内または説明欄に以下の形式のクレジットを記載してください**:

```
"<曲名>" Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0 License
http://creativecommons.org/licenses/by/4.0/
```

## 差し替えについて
外部音源を追加する場合は、**商用利用可・再配布可**のライセンスであることを確認し、
`app/tracks.py` の `credit` / `license` を正確に記載してください。
