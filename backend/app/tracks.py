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
DEFAULT_TRACK_ID = "calm"


def get_track(track_id: str) -> Optional[Track]:
    return next((t for t in TRACKS if t.id == track_id), None)


def resolve(track_id: str, image_count: int) -> Optional[Track]:
    """track_id を Track に解決する。

    - "auto" または未知/空 → 画像枚数で決定的に自動選曲（毎回同じ入力なら同じ曲）。
    - それ以外 → 該当 Track（無ければ None で呼び出し側が 400 判定）。
    """
    if not track_id or track_id == AUTO:
        return TRACKS[image_count % len(TRACKS)] if TRACKS else None
    return get_track(track_id)


def track_path(music_dir: Path, track: Track) -> Path:
    return music_dir / track.filename
