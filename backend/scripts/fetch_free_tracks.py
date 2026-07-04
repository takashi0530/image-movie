"""フリー音楽（Kevin MacLeod / incompetech.com, CC BY 4.0）を取得して同梱用に整える。

CC BY 4.0 は再配布・改変を明示的に許可している（要クレジット表記）。
クレジットは app/tracks.py の credit と assets/music/CREDITS.md、および UI に表示する。

処理: ダウンロード → 先頭95秒にトリム → ラウドネス正規化(-14LUFS) → 末尾3秒フェード
      → AAC 192k で assets/music/<id>.aac に出力。

使い方:
    cd backend && source .venv/bin/activate && python scripts/fetch_free_tracks.py
"""
from __future__ import annotations

import subprocess
import tempfile
import urllib.request
from pathlib import Path

import imageio_ffmpeg

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "music"
BASE = "https://incompetech.com/music/royalty-free/mp3-royaltyfree"

CLIP_SECONDS = 95
FADE_SECONDS = 3

# id → (曲名, 出力ファイル名)。曲名は incompetech のカタログ名そのまま。
TRACKS = {
    "upbeat": "Monkeys Spinning Monkeys",
    "cafe": "Lobby Time",
    "bossa": "Bossa Antigua",
    "pop": "Carefree",
    "dance": "Disco con Tutti",
    "house": "Voxel Revolution",
    "electro": "Electrodoodle",
}


def fetch(title: str, dest: Path) -> None:
    url = f"{BASE}/{urllib.request.quote(title)}.mp3"
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "image-movie-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as res, dest.open("wb") as out:
        while chunk := res.read(1 << 16):
            out.write(chunk)


def transcode(src: Path, dest: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    fade_start = CLIP_SECONDS - FADE_SECONDS
    proc = subprocess.run(
        [
            ffmpeg, "-y", "-i", str(src),
            "-t", str(CLIP_SECONDS),
            "-af", f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={fade_start}:d={FADE_SECONDS}",
            "-c:a", "aac", "-b:a", "192k",
            str(dest),
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1000:])


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for track_id, title in TRACKS.items():
        print(f"{track_id}: {title}")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            fetch(title, tmp_path)
            out = ASSETS / f"{track_id}.aac"
            transcode(tmp_path, out)
            print(f"  -> {out.name} ({out.stat().st_size // 1024}KB)")
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
