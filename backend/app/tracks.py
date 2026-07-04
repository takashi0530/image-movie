"""BGM トラックのレジストリ。

同梱音源は scripts/generate_sample_tracks.py で生成したオリジナル曲（CC0 相当・再配布可）。
差し替える場合は assets/music/ にファイルを置き、下の TRACKS を更新する。
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


TRACKS: List[Track] = [
    Track("calm", "おだやか", "calm.aac", "Procedurally generated original", "CC0"),
    Track("happy", "あかるい", "happy.aac", "Procedurally generated original", "CC0"),
    Track("epic", "壮大", "epic.aac", "Procedurally generated original", "CC0"),
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
