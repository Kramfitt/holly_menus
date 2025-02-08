import argparse
from PIL import Image
import pytesseract
import os

# Change to the output_images directory
os.chdir("C:\\Users\\OEM\\Downloads\\HollyMenus\\output_images")
print(f"Current working directory: {os.getcwd()}")  # Debug: Print current directory

def detect_orientation(image_path):
    """
    Detect the orientation of an image using pytesseract OSD (Orientation and Script Detection).

    Args:
        image_path (str): Path to the image file.

    Returns:
        int: The angle of rotation (0, 90, 180, 270).
    """
    try:
        image = Image.open(image_path)
        osd_data = pytesseract.image_to_osd(image)
        rotation_angle = int(osd_data.split("Rotate:")[1].split("\n")[0].strip())
        print(f"Detected rotation: {rotation_angle}°")
        return rotation_angle
    except Exception as e:
        print(f"Error detecting orientation: {e}")
        return 0

def correct_orientation(image_path, output_path):
    """
    Correct the orientation of an image based on detected rotation.

    Args:
        image_path (str): Path to the image file.
        output_path (str): Path to save the corrected image.
    """
    print(f"Processing file: {image_path}")
    rotation_angle = detect_orientation(image_path)
    try:
        image = Image.open(image_path)
        if rotation_angle in [90, 180, 270]:
            corrected_image = image.rotate(360 - rotation_angle, expand=True)
            corrected_image.save(output_path)
            print(f"Corrected image saved to: {output_path}")
        else:
            print("No rotation needed; saving as is.")
            image.save(output_path)
            print(f"File saved to: {output_path}")
    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect and correct image orientation")
    parser.add_argument("image_path", type=str, help="Path to the input image file")
    parser.add_argument("--output", type=str, default="corrected_image.png", help="Path to save the corrected image")

    args = parser.parse_args()

    # Correct the image orientation
    correct_orientation(args.image_path, args.output)
