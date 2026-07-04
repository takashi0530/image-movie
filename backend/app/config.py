"""アプリケーション設定。環境変数 `IMAGE_MOVIE_*` で上書き可能。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ ディレクトリ。パスはすべてここを基準に絶対化し、cwd 依存をなくす。
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMAGE_MOVIE_", env_file=".env")

    # 動画設定
    width: int = 1920
    height: int = 1080
    seconds_per_image: float = 2.5  # 1枚あたりの表示秒数
    output_fps: int = 30            # 出力動画のフレームレート（再生互換性のため通常値）
    music_dir: Path = BASE_DIR / "assets" / "music"  # 選択可能な BGM 音源を置くディレクトリ

    # ストレージ
    work_dir: Path = BASE_DIR / "tmp" / "jobs"
    job_ttl_seconds: int = 3600     # この秒数を過ぎたジョブの作業ディレクトリを削除

    # アップロード制限
    max_files: int = 300
    max_file_size_mb: int = 25
    allowed_extensions: List[str] = [".jpg", ".jpeg", ".png", ".webp"]

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]

    @property
    def input_framerate(self) -> float:
        """入力フレームレート（= 1 / 表示秒数）。"""
        return 1.0 / self.seconds_per_image

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    return settings
