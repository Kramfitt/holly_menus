from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import os
import argparse

def convert_pdf_to_images(pdf_path, output_folder, poppler_path):
    """
    Convert a PDF into images.
    """
    os.makedirs(output_folder, exist_ok=True)
    images = convert_from_path(pdf_path, poppler_path=poppler_path)
    image_paths = []

    for i, image in enumerate(images):
        # Save each page as an image
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        image_path = os.path.join(output_folder, f"{pdf_basename}_page_{i + 1}.png")
        image.save(image_path, "PNG")
        image_paths.append(image_path)
        print(f"Saved: {image_path}")

    return image_paths

def detect_orientation(image_path):
    """
    Detect the orientation of an image.
    """
    try:
        image = Image.open(image_path)
        osd_data = pytesseract.image_to_osd(image)
        rotation_angle = int(osd_data.split("Rotate:")[1].split("\n")[0].strip())
        return rotation_angle
    except Exception as e:
        print(f"Error detecting orientation: {e}")
        return 0

def correct_orientation(image_path, output_path):
    """
    Correct the orientation of an image based on detected rotation.
    """
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
    parser = argparse.ArgumentParser(description="Convert PDF to images and correct orientation")
    parser.add_argument("pdf_path", type=str, help="Path to the input PDF file")
    parser.add_argument("--output_folder", type=str, default="./output_images", help="Folder to save images")
    parser.add_argument("--poppler_path", type=str, default="C:\\Poppler\\Release-24.08.0-0\\poppler-24.08.0\\Library\\bin", help="Path to Poppler binaries")

    args = parser.parse_args()

    # Convert PDF to images
    image_paths = convert_pdf_to_images(args.pdf_path, args.output_folder, args.poppler_path)

    # Correct orientation for each image
    for image_path in image_paths:
        output_path = image_path.replace(".png", "_corrected.png")
        correct_orientation(image_path, output_path)
