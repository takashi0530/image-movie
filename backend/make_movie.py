# 標準ライブラリのインポート
import glob
import os
import shutil
from typing import List, Tuple, Union

# 関連外部ライブラリ（サードパーティ）のインポート
import cv2
import numpy as np
from moviepy.editor import AudioFileClip, VideoFileClip, vfx

# Constants
# DESIRED_WIDTH = 5760  # 4k 3:2
# DESIRED_HEIGHT = 3840 # 4k 3:2
DESIRED_WIDTH = 1920  # フルHD 1920x1080
DESIRED_HEIGHT = 1080 # フルHD 1920x1080
AUDIO_PATH = "music/am.aac"
OUTPUT_VIDEO_FILE_NAME = "only_movie.mp4"
OUTPUT_VIDEO_WITH_MUSIC_FILE_NAME = "music_movie.mp4"

def rename_images(directory_path: str) -> str:
    output_dir = os.path.join(directory_path, "result")
    os.makedirs(output_dir, exist_ok=True)

    image_paths = glob.glob(os.path.join(directory_path, '*.[jJ][pP][eE]*[gG]'))

    for idx, image in enumerate(image_paths, start=1):
        _, ext = os.path.splitext(image)
        new_filename = f"{idx:04}{ext}"
        new_filepath = os.path.join(output_dir, new_filename)
        shutil.copy(image, new_filepath)

    print(f"Images have been copied with new names to {output_dir}.")
    return output_dir

def resize_without_crop(img: np.ndarray, desired_width: int, desired_height: int) -> np.ndarray:
    original_height, original_width = img.shape[:2]
    aspect_ratio = original_width / original_height
    desired_aspect_ratio = desired_width / desired_height

    if aspect_ratio > desired_aspect_ratio:
        new_width = desired_width
        new_height = int(desired_width / aspect_ratio)
    else:
        new_height = desired_height
        new_width = int(desired_height * aspect_ratio)

    # Ensure the new dimensions are not larger than the desired dimensions
    new_width = min(new_width, desired_width)
    new_height = min(new_height, desired_height)

    resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # Check if resizing is necessary
    if new_width == desired_width and new_height == desired_height:
        return resized_img
    else:
        # Create a black canvas to fit the desired dimensions
        canvas = np.zeros((desired_height, desired_width, 3), dtype=np.uint8)
        # Calculate the centering position
        y_offset = (desired_height - new_height) // 2
        x_offset = (desired_width - new_width) // 2
        # Place the resized image in the center of the canvas
        canvas[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = resized_img
        return canvas

def resize_and_center(img: np.ndarray, desired_width: int, desired_height: int) -> np.ndarray:
    resized_img = resize_without_crop(img, desired_width, desired_height)
    height, width = resized_img.shape[:2]

    # Create a black canvas with the desired dimensions
    background = np.zeros((desired_height, desired_width, 3), dtype=np.uint8)

    # Calculate offsets to center the image
    y_offset = (desired_height - height) // 2
    x_offset = (desired_width - width) // 2

    # Place the resized image onto the canvas
    background[y_offset:y_offset+height, x_offset:x_offset+width] = resized_img
    return background

def calculate_offsets(background_shape: Tuple[int, int, int], resized_shape: Tuple[int, int, int]) -> Tuple[int, int]:
    y_offset = (background_shape[0] - resized_shape[0]) # 2
    x_offset = (background_shape[1] - resized_shape[1]) # 2
    return y_offset, x_offset

def add_music_to_video(video_path: str, audio_path: str, output_path: str) -> None:
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)
    video_duration = video.duration
    audio_repeated = audio.fx(vfx.loop, duration=video_duration)
    video_with_audio = video.set_audio(audio_repeated)
    video_with_audio.write_videofile(output_path, codec='libx264')

def remove_directory(dir_path: str) -> None:
    if os.path.exists(dir_path) and os.path.isdir(dir_path):
        shutil.rmtree(dir_path)
        print(f"ディレクトリを削除しました: {dir_path}")
    else:
        print(f"削除対象のディレクトリがみつかりません: {dir_path}")

def find_image_files(temp_dir: str) -> List[str]:
    data_path_jpg: str = os.path.join(temp_dir, '*.[jJ][pP][gG]')
    data_path_jpeg: str = os.path.join(temp_dir, '*.[jJ][pP][eE][gG]')
    data_path_png: str = os.path.join(temp_dir, '*.[pP][nN][gG]')
    data_path_webp: str = os.path.join(temp_dir, '*.[wW][eE][bB][pP]')
    files_jpg: List[str] = sorted(glob.glob(data_path_jpg))
    files_jpeg: List[str] = sorted(glob.glob(data_path_jpeg))
    files_png: List[str] = sorted(glob.glob(data_path_png))
    files_webp: List[str] = sorted(glob.glob(data_path_webp))
    files: List[str] = files_jpg + files_jpeg + files_png + files_webp  # jpg, jpeg, png, と webp のリストを結合
    return files

def main(temp_dir: str) -> None:
    files = find_image_files(temp_dir)
    # 音楽なし動画の保存先path
    output_unique_dir =  os.path.join(temp_dir, OUTPUT_VIDEO_FILE_NAME)

    # H.264コーデックを使用してビデオライターを作成
    fourcc = cv2.VideoWriter_fourcc(*'X264')
    # 音楽なし動画の作成
    video = cv2.VideoWriter(output_unique_dir, fourcc, 0.4, (DESIRED_WIDTH, DESIRED_HEIGHT))

    # 音楽なし動画に画像を追加
    for file in files:
        img = cv2.imread(file, cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"Image not loaded: {file}")
            continue

        # PNGやWEBPファイルの場合、アルファチャネルを取り扱う必要があるかもしれない
        if img.shape[2] == 4:  # アルファチャネルが存在する場合
            # アルファチャネルをRGBに変換する
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        try:
            img = resize_and_center(img, DESIRED_WIDTH, DESIRED_HEIGHT)
            video.write(img)
        except Exception as e:
            print(f"Error on file {file}: {e}")
            break
        # 画像の解放
        del img

    # 動画ファイルの書き込み完了処理
    video.release()

    # 音楽付き動画の保存先path
    output_video_with_music = os.path.join(temp_dir, OUTPUT_VIDEO_WITH_MUSIC_FILE_NAME)

    # 音楽付き動画の作成
    add_music_to_video(output_unique_dir, AUDIO_PATH, output_video_with_music)
    # 音楽付き動画の削除
    # remove_directory(temp_dir)


if __name__ == "__main__":
    main()
