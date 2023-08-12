import os
import glob
import cv2
import shutil
import numpy as np

from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, vfx, concatenate_videoclips
from moviepy.audio.fx.all import audio_fadeout

# Constants
DESIRED_WIDTH = 749
DESIRED_HEIGHT = 1000
# DESIRED_WIDTH = 1000
# DESIRED_HEIGHT = 749

IMAGE_DIR = "target_images"
AUDIO_PATH = "music/am.mp3"
OUTPUT_VIDEO_NAME = "output_movie/movie.mp4"
OUTPUT_VIDEO_WITH_MUSIC_NAME = "output_movie/music_movie.mp4"

# def rename_images(directory_path: str):
#     output_dir = os.path.join(directory_path, "result")
#     os.makedirs(output_dir, exist_ok=True)

#     image_paths = [os.path.join(directory_path, f) for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]

#     for idx, image in enumerate(image_paths, start=1):
#         _, ext = os.path.splitext(image)
#         if ext.lower() in ['.jpeg', '.jpg']:
#             new_filename = f"{idx:04}{ext}"
#             new_filepath = os.path.join(output_dir, new_filename)
#             shutil.copy(image, new_filepath)

#     print(f"Images have been copied with new names to {output_dir}.")
#     return output_dir

def resize_without_crop(img, desired_width, desired_height):
    original_height, original_width = img.shape[:2]
    aspect_ratio = original_width / original_height
    desired_aspect_ratio = desired_width / desired_height

    if aspect_ratio > desired_aspect_ratio:
        new_width = desired_width
        new_height = int(desired_width / aspect_ratio)
    else:
        new_height = desired_height
        new_width = int(desired_height * aspect_ratio)

    return cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

def resize_and_center(img, desired_width, desired_height):
    resized_img = resize_without_crop(img, desired_width, desired_height)
    background = np.zeros((desired_height, desired_width, 3), dtype=np.uint8)
    y_offset = (desired_height - resized_img.shape[0]) // 2
    x_offset = (desired_width - resized_img.shape[1]) // 2
    background[y_offset:y_offset+resized_img.shape[0], x_offset:x_offset+resized_img.shape[1]] = resized_img
    return background

def add_music_to_video(video_path, audio_path, output_path):
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)
    video_duration = video.duration
    audio_duration = audio.duration
    repeat_count = int(video_duration // audio_duration) + 1
    audio_repeated = audio.fx(vfx.loop, duration=video_duration)
    video_with_audio = video.set_audio(audio_repeated)
    video_with_audio.write_videofile(output_path, codec='libx264')

def remove_file(filepath: str):
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"Removed file: {filepath}")
    else:
        print(f"File not found: {filepath}")

# Call the function
# output_dir = rename_images(IMAGE_DIR)
# data_path = os.path.join(output_dir,'*.jpeg')
data_path = os.path.join(IMAGE_DIR,'*.jpeg')
files = glob.glob(data_path)
files.sort()

video = cv2.VideoWriter(OUTPUT_VIDEO_NAME, cv2.VideoWriter_fourcc(*'mp4v'), 1, (DESIRED_WIDTH, DESIRED_HEIGHT))
for i, file in enumerate(files):
    img = cv2.imread(file)
    if img is None:
        print(f"Image not loaded: {file}")
        continue
    try:
        img = resize_and_center(img, DESIRED_WIDTH, DESIRED_HEIGHT)
        video.write(img)
    except Exception as e:
        print(f"Error on file {file}: {e}")
        break

cv2.destroyAllWindows()
video.release()

add_music_to_video(OUTPUT_VIDEO_NAME, AUDIO_PATH, OUTPUT_VIDEO_WITH_MUSIC_NAME)
remove_file(OUTPUT_VIDEO_NAME)


