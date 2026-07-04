"""正規化済みフレームと音源から MP4 を1回のエンコードで生成する。

cv2.VideoWriter + moviepy の二重エンコードを廃し、imageio-ffmpeg 同梱の
ffmpeg バイナリで libx264 + aac を一括生成する（高速・H.264/AAC が確実）。
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import imageio_ffmpeg


class VideoEncodeError(Exception):
    pass


def build_video(
    frames_dir: Path,
    audio_path: Optional[Path],
    output_path: Path,
    *,
    input_framerate: float,
    output_fps: int,
) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    has_audio = audio_path is not None
    if has_audio and not Path(audio_path).is_file():
        # 指定された音源が無いのに黙って無音動画を作らない（None 指定のみ無音を許可）
        raise VideoEncodeError(f"音源ファイルがありません: {audio_path}")

    cmd = [
        ffmpeg,
        "-y",
        "-framerate", str(input_framerate),
        "-i", str(frames_dir / "%04d.png"),
    ]
    if has_audio:
        # 音源を動画の長さに合わせて無限ループ
        cmd += ["-stream_loop", "-1", "-i", str(audio_path)]

    cmd += [
        "-r", str(output_fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",  # 幅広いプレイヤーとの互換性
    ]
    if has_audio:
        cmd += [
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",  # 動画の長さで終了（無限ループ音源を打ち切る）
        ]
    cmd += [str(output_path)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # ffmpeg のエラー末尾のみ保持（巨大な進捗ログを避ける）
        raise VideoEncodeError(proc.stderr[-2000:] if proc.stderr else "ffmpeg failed")
