import cv2
import os
import sys
import glob

def rotate_image(img, angle):
    if angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    else:
        raise ValueError("Angle must be 90, 180, or 270")

def rotate_images(input_dir, output_dir, angle):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    image_paths = glob.glob(os.path.join(input_dir, '*'))

    for image_path in image_paths:
        image_name = os.path.basename(image_path)
        img = cv2.imread(image_path)
        if img is None:
            continue

        try:
            img_rotated = rotate_image(img, angle)
            cv2.imwrite(os.path.join(output_dir, image_name), img_rotated)
        except Exception as e:
            print(f"Error rotating image {image_name}: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python rotate_images.py <input_dir> <output_dir> <angle>")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    angle = int(sys.argv[3])

    if angle not in [90, 180, 270]:
        print("Error: angle must be 90, 180, or 270")
        sys.exit(1)

    rotate_images(input_dir, output_dir, angle)
