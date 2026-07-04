"""BGM トラックのレジストリ。

同梱音源は Kevin MacLeod (incompetech.com) の CC BY 4.0 楽曲
（再配布・改変可、要クレジット表記）。取得と整音は scripts/fetch_free_tracks.py。
CC BY のクレジットは UI に可視表示する（assets/music/CREDITS.md 参照）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    filename: str
    credit: str
    license: str


_KM = 'Music: Kevin MacLeod (incompetech.com)'
_CC = "CC BY 4.0"

TRACKS: List[Track] = [
    Track("upbeat", "アップテンポ", "upbeat.aac", f'"Monkeys Spinning Monkeys" {_KM}', _CC),
    Track("pop", "ポップ", "pop.aac", f'"Carefree" {_KM}', _CC),
    Track("cafe", "カフェ", "cafe.aac", f'"Lobby Time" {_KM}', _CC),
    Track("bossa", "ボサノバ", "bossa.aac", f'"Bossa Antigua" {_KM}', _CC),
    Track("dance", "ダンス", "dance.aac", f'"Disco con Tutti" {_KM}', _CC),
    Track("house", "ハウス", "house.aac", f'"Voxel Revolution" {_KM}', _CC),
    Track("electro", "エレクトロ", "electro.aac", f'"Electrodoodle" {_KM}', _CC),
]

AUTO = "auto"


def get_track(track_id: str) -> Optional[Track]:
    return next((t for t in TRACKS if t.id == track_id), None)


def resolve(track_id: str, image_count: int) -> Optional[Track]:
    """track_id を Track に解決する。

    - "auto" → 画像枚数で決定的に自動選曲（同じ入力なら同じ曲）。
    - 既知の id → 該当 Track。
    - 空文字・未知の id → None（呼び出し側が 400 を返す）。
      空文字を黙って auto に落とすとクライアント側の欠落バグを隠すため、明示的に拒否する。
    """
    if track_id == AUTO:
        return TRACKS[image_count % len(TRACKS)]
    return get_track(track_id)


def track_path(music_dir: Path, track: Track) -> Path:
    return music_dir / track.filename
