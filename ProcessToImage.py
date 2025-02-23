import sys
import shutil
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import os
import argparse
from typing import List, Optional
import platform

def check_dependencies() -> bool:
    """
    Check if all required dependencies are installed and accessible.
    """
    # Check Tesseract installation
    if not shutil.which('tesseract'):
        print("Error: Tesseract is not installed or not in PATH")
        print("Please install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
        return False

    # Check Poppler installation
    try:
        from pdf2image.exceptions import PDFPageCountError
        # Try to find pdftoppm in PATH
        if not shutil.which('pdftoppm') and platform.system() != 'Windows':
            print("Error: Poppler (pdftoppm) is not installed or not in PATH")
            print("Please install poppler-utils package")
            return False
    except ImportError:
        print("Error: pdf2image package is not properly installed")
        print("Please run: pip install pdf2image==1.17.0")
        return False

    return True

def get_poppler_path() -> Optional[str]:
    """
    Get the appropriate Poppler path based on the operating system.
    """
    if platform.system() == 'Windows':
        return "C:\\Poppler\\Release-24.08.0-0\\poppler-24.08.0\\Library\\bin"
    else:
        # On Linux/Unix, Poppler should be in the system PATH
        return None

def convert_pdf_to_images(pdf_path: str, output_folder: str, poppler_path: Optional[str] = None) -> List[str]:
    """
    Convert a PDF into images.
    
    Args:
        pdf_path (str): Path to the PDF file
        output_folder (str): Directory to save the images
        poppler_path (str, optional): Path to Poppler binaries, not needed on Linux if installed system-wide
        
    Returns:
        List[str]: List of paths to the generated images
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Convert output_folder to absolute path for clearer messaging
    output_folder = os.path.abspath(output_folder)
    os.makedirs(output_folder, exist_ok=True)
    print(f"\nOutput directory: {output_folder}")

    try:
        # On Linux, we don't need to specify poppler_path if it's installed system-wide
        if platform.system() != 'Windows':
            images = convert_from_path(pdf_path)
        else:
            images = convert_from_path(pdf_path, poppler_path=poppler_path)
    except Exception as e:
        print(f"Error converting PDF: {e}")
        print("Please check if Poppler is properly installed and the path is correct")
        if platform.system() == 'Windows':
            print(f"Windows Poppler path: {poppler_path}")
        else:
            print("On Linux, ensure poppler-utils is installed")
        return []

    image_paths = []
    total_pages = len(images)
    print(f"\nConverting {total_pages} pages to images...")

    for i, image in enumerate(images):
        try:
            # Save each page as an image
            pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
            image_path = os.path.join(output_folder, f"{pdf_basename}_page_{i + 1}.png")
            image.save(image_path, "PNG")
            image_paths.append(image_path)
            print(f"Progress: {i + 1}/{total_pages} pages processed - Saved as: {os.path.basename(image_path)}")
        except Exception as e:
            print(f"Error saving page {i + 1}: {e}")
            continue

    return image_paths

def detect_orientation(image_path: str) -> int:
    """
    Detect the orientation of an image.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        int: Detected rotation angle
    """
    try:
        image = Image.open(image_path)
        osd_data = pytesseract.image_to_osd(image)
        rotation_angle = int(osd_data.split("Rotate:")[1].split("\n")[0].strip())
        return rotation_angle
    except Exception as e:
        print(f"Error detecting orientation for {image_path}: {e}")
        return 0

def correct_orientation(image_path: str, output_path: str) -> None:
    """
    Correct the orientation of an image based on detected rotation.
    
    Args:
        image_path (str): Path to the input image
        output_path (str): Path to save the corrected image
    """
    if not os.path.exists(image_path):
        print(f"Error: Input image not found: {image_path}")
        return

    rotation_angle = detect_orientation(image_path)
    try:
        image = Image.open(image_path)
        if rotation_angle in [90, 180, 270]:
            corrected_image = image.rotate(360 - rotation_angle, expand=True)
            corrected_image.save(output_path)
            print(f"Corrected image saved as: {os.path.basename(output_path)}")
        else:
            print(f"No rotation needed for: {os.path.basename(image_path)}")
            image.save(output_path)
    except Exception as e:
        print(f"Error processing {image_path}: {e}")

def main():
    """Main function to handle the PDF processing workflow."""
    parser = argparse.ArgumentParser(description="Convert PDF to images and correct orientation")
    parser.add_argument("pdf_path", type=str, help="Path to the input PDF file")
    parser.add_argument("--output_folder", type=str, default="./output_images", 
                       help="Folder to save images")
    parser.add_argument("--poppler_path", type=str, 
                       default=get_poppler_path(),
                       help="Path to Poppler binaries (not needed on Linux if installed system-wide)")

    args = parser.parse_args()

    # Check dependencies before proceeding
    if not check_dependencies():
        sys.exit(1)

    try:
        # Convert PDF to images
        print(f"\nProcessing PDF: {args.pdf_path}")
        image_paths = convert_pdf_to_images(args.pdf_path, args.output_folder, args.poppler_path)

        if not image_paths:
            print("No images were generated. Please check the PDF file and try again.")
            sys.exit(1)

        # Correct orientation for each image
        print("\nCorrecting image orientations...")
        for image_path in image_paths:
            output_path = image_path.replace(".png", "_corrected.png")
            correct_orientation(image_path, output_path)

        # Show final summary
        output_dir = os.path.abspath(args.output_folder)
        print(f"\nProcessing complete!")
        print(f"All files have been saved to: {output_dir}")
        print(f"Original images are named: [pdf_name]_page_[number].png")
        print(f"Corrected images are named: [pdf_name]_page_[number]_corrected.png")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 