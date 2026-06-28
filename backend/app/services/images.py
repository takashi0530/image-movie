"""画像の検証と正規化（リサイズ + 中央寄せ + 黒背景パディング + 任意回転）。"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np


class ValidationError(Exception):
    """ユーザー起因の入力エラー（400 として返す）。"""


def validate_uploads(
    filenames: Sequence[str],
    sizes: Sequence[int],
    *,
    allowed_extensions: Sequence[str],
    max_files: int,
    max_file_size_bytes: int,
) -> None:
    if not filenames:
        raise ValidationError("画像が選択されていません")
    if len(filenames) > max_files:
        raise ValidationError(f"画像は最大 {max_files} 枚までです")
    for name, size in zip(filenames, sizes):
        ext = Path(name).suffix.lower()
        if ext not in allowed_extensions:
            raise ValidationError(f"対応していない拡張子です: {name}")
        if size > max_file_size_bytes:
            limit_mb = max_file_size_bytes // (1024 * 1024)
            raise ValidationError(f"ファイルサイズが大きすぎます（上限 {limit_mb}MB）: {name}")


def _rotate(img: np.ndarray, rotation: int) -> np.ndarray:
    if rotation == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if rotation == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def _fit_with_padding(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """アスペクト比を保ってフレーム内に収め、余白を黒で中央パディングする。"""
    h, w = img.shape[:2]
    scale = min(width / w, height / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    y_offset = (height - new_h) // 2
    x_offset = (width - new_w) // 2
    canvas[y_offset : y_offset + new_h, x_offset : x_offset + new_w] = resized
    return canvas


def _to_bgr(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:  # グレースケール
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:  # アルファチャネルあり
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def normalize_images(
    src_paths: Iterable[Path],
    frames_dir: Path,
    *,
    width: int,
    height: int,
    rotation: int = 0,
) -> int:
    """各画像を正規化し、連番 PNG（0001.png ...）として frames_dir に書き出す。

    書き出した枚数を返す。有効な画像が 0 枚なら ValidationError。
    """
    frames_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in src_paths:
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is None:
            continue
        img = _to_bgr(img)
        img = _rotate(img, rotation)
        frame = _fit_with_padding(img, width, height)
        count += 1
        cv2.imwrite(str(frames_dir / f"{count:04d}.png"), frame)

    if count == 0:
        raise ValidationError("有効な画像がありませんでした")
    return count
