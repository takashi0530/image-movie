import numpy as np
import pytest

from app.services import images as image_service


def _write_image(path, w, h, channels=3):
    import cv2

    if channels == 4:
        img = np.full((h, w, 4), 200, dtype=np.uint8)
    else:
        img = np.full((h, w, 3), 128, dtype=np.uint8)
    cv2.imwrite(str(path), img)


def test_validate_uploads_rejects_bad_extension():
    with pytest.raises(image_service.ValidationError):
        image_service.validate_uploads(
            ["a.gif"], [10],
            allowed_extensions=[".jpg", ".png"], max_files=10, max_file_size_bytes=1000,
        )


def test_validate_uploads_rejects_too_many():
    with pytest.raises(image_service.ValidationError):
        image_service.validate_uploads(
            ["a.jpg", "b.jpg"], [10, 10],
            allowed_extensions=[".jpg"], max_files=1, max_file_size_bytes=1000,
        )


def test_validate_uploads_rejects_oversize():
    with pytest.raises(image_service.ValidationError):
        image_service.validate_uploads(
            ["a.jpg"], [2000],
            allowed_extensions=[".jpg"], max_files=10, max_file_size_bytes=1000,
        )


def test_normalize_images_pads_to_target(tmp_path):
    src = tmp_path / "src.png"
    _write_image(src, 100, 50)  # 2:1 を 16:9 キャンバスへ
    frames_dir = tmp_path / "frames"

    count = image_service.normalize_images(
        [src], frames_dir, width=1920, height=1080, rotation=0
    )

    assert count == 1
    import cv2

    frame = cv2.imread(str(frames_dir / "0001.jpg"))
    assert frame.shape == (1080, 1920, 3)


def test_normalize_images_handles_alpha_and_rotation(tmp_path):
    src = tmp_path / "src.png"
    _write_image(src, 80, 40, channels=4)
    frames_dir = tmp_path / "frames"

    count = image_service.normalize_images(
        [src], frames_dir, width=1920, height=1080, rotation=90
    )
    assert count == 1


def test_normalize_images_empty_raises(tmp_path):
    frames_dir = tmp_path / "frames"
    with pytest.raises(image_service.ValidationError):
        image_service.normalize_images([], frames_dir, width=10, height=10)


def test_normalize_images_rejects_oversized_pixels(tmp_path, monkeypatch):
    """ピクセル数上限を超える画像（展開爆弾対策）は無効として扱う。"""
    src = tmp_path / "src.png"
    _write_image(src, 20, 20)  # 400px
    monkeypatch.setattr(image_service, "MAX_IMAGE_PIXELS", 100)  # 上限を下回らせる
    with pytest.raises(image_service.ValidationError):  # 有効画像0枚扱い
        image_service.normalize_images(
            [src], tmp_path / "frames", width=100, height=100
        )
