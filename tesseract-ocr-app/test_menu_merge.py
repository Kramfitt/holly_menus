import os
import sys
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
import pytesseract
import re
from datetime import datetime
import gc
from typing import Dict, Optional, Tuple
import logging
import cv2
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def print_debug_info():
    """Print debug information about the environment"""
    print("\nDebug Information:")
    print(f"Current working directory: {os.getcwd()}")
    print(f"TESSDATA_PREFIX: {os.environ.get('TESSDATA_PREFIX', 'Not set')}")
    print(f"PATH: {os.environ.get('PATH', 'Not set')}")
    print(f"Tesseract command: {pytesseract.pytesseract.tesseract_cmd}")
    
    try:
        version = pytesseract.get_tesseract_version()
        print(f"Tesseract version: {version}")
    except Exception as e:
        print(f"Error getting Tesseract version: {e}")
    
    try:
        langs = pytesseract.get_languages()
        print(f"Available languages: {langs}")
    except Exception as e:
        print(f"Error getting languages: {e}")

def extract_dates_from_image(image_path: str) -> Optional[Dict[str, str]]:
    """Extract dates from the image using OCR"""
    try:
        print(f"Processing image: {image_path}")
        print(f"Tesseract command: {pytesseract.pytesseract.tesseract_cmd}")
        
        # Open and optimize image for OCR
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode not in ('L', 'RGB'):
                img = img.convert('RGB')
            
            # Resize if too large (max dimension 2400px)
            max_dimension = 2400
            if max(img.size) > max_dimension:
                ratio = max_dimension / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Enhance image for OCR
            img = ImageEnhance.Contrast(img).enhance(1.5)
            img = ImageEnhance.Sharpness(img).enhance(1.5)
            
            # Convert to grayscale for OCR
            img = img.convert('L')
            
            # Use custom OCR config for better memory usage
            custom_config = '--psm 6 --oem 1'
            text = pytesseract.image_to_string(img, config=custom_config)
            print(f"Extracted text:\n{text}")
            
            # Clean up memory
            img = None
            
        # Process text to extract dates
        dates = {}
        lines = text.split('\n')
        for line in lines:
            # Process one line at a time
            match = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s+(\d+(?:st|nd|rd|th)?\s+[A-Za-z]+)', line)
            if match:
                day = match.group(1)[:3]  # Standardize to 3 letters
                date = match.group(2)
                dates[day] = date
        
        print(f"Extracted dates: {dates}")
        return dates if dates else None
        
    except Exception as e:
        print(f"Error extracting dates: {str(e)}")
        return None
    finally:
        # Ensure we clean up any temporary files
        if 'img' in locals():
            del img
        gc.collect()

def add_dates_to_menu(master_path: str, dates: Dict[str, str], output_path: str) -> bool:
    """Add dates to the master menu template"""
    temp_file = None
    try:
        # Create a temporary PDF for the dates overlay
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        
        # Create the canvas
        c = canvas.Canvas(temp_file.name, pagesize=letter)
        
        # Define positions for each day's date
        date_positions = {
            'Mon': (100, 700),  # X, Y coordinates
            'Tue': (200, 700),
            'Wed': (300, 700),
            'Thu': (400, 700),
            'Fri': (500, 700),
            'Sat': (600, 700),
            'Sun': (700, 700)
        }
        
        # Add each date to the canvas
        for day, date in dates.items():
            if day in date_positions:
                x, y = date_positions[day]
                c.drawString(x, y, date)
        
        c.save()
        
        # Close the temp file before reading it
        temp_file.close()
        
        # Merge the overlay with the master template
        with open(master_path, 'rb') as master_file, \
             open(temp_file.name, 'rb') as overlay_file, \
             open(output_path, 'wb') as output_file:
            
            master = PdfReader(master_file)
            overlay = PdfReader(overlay_file)
            output = PdfWriter()
            
            # Merge first pages
            page = master.pages[0]
            page.merge_page(overlay.pages[0])
            output.add_page(page)
            
            # Add any remaining pages from master
            for page in master.pages[1:]:
                output.add_page(page)
            
            # Write the output
            output.write(output_file)
            
        return True
        
    except Exception as e:
        print(f"Error adding dates to menu: {e}")
        return False
    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                print(f"Warning: Failed to delete temp file: {e}")

def merge_header_with_template(source_image: str, template_path: str, header_proportion: float = 0.12) -> Optional[str]:
    """Copy header from source image to template"""
    try:
        # Read images
        source = cv2.imread(source_image)
        template = cv2.imread(template_path)
        
        if source is None or template is None:
            print("Failed to read source or template image")
            return None
        
        # Get dimensions
        source_height = source.shape[0]
        template_height = template.shape[0]
        template_width = template.shape[1]
        
        # Copy header using specified proportion
        header_height = int(source_height * header_proportion)
        template_header_height = int(template_height * header_proportion)
        
        # Extract header
        header = source[0:header_height, :]
        
        # Calculate the aspect ratio of the header
        header_aspect_ratio = header.shape[1] / header.shape[0]
        
        # Calculate new header width maintaining aspect ratio
        new_header_width = int(template_header_height * header_aspect_ratio)
        
        # Resize header maintaining aspect ratio
        header_resized = cv2.resize(header, (new_header_width, template_header_height))
        
        # Create new image
        result = template.copy()
        
        # Calculate centering position
        x_offset = (template_width - new_header_width) // 2
        
        # If header is wider than template, crop it from center
        if new_header_width > template_width:
            crop_start = (new_header_width - template_width) // 2
            header_resized = header_resized[:, crop_start:crop_start + template_width]
            x_offset = 0
        
        # Create the header region with white background
        header_region = np.full((template_header_height, template_width, 3), 255, dtype=np.uint8)
        
        # Place the resized header in the center
        if x_offset >= 0:
            header_region[:, x_offset:x_offset + header_resized.shape[1]] = header_resized
        
        # Copy the header region to the template
        result[0:template_header_height, :] = header_region
        
        # Save result with unique timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        output_path = os.path.join(
            'temp_images',
            f'merged_menu_{timestamp}.png'
        )
        
        # Ensure output directory exists
        os.makedirs('temp_images', exist_ok=True)
        
        # Save and verify
        success = cv2.imwrite(output_path, result)
        if not success:
            print("Failed to save merged image")
            return None
        
        print(f"Successfully merged header with template: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Error merging header with template: {e}")
        return None

def test_menu_processing():
    """Test the menu processing functionality"""
    try:
        print("\nStarting test_menu_processing...")
        print_debug_info()
        
        # Create test directories
        os.makedirs('temp_images', exist_ok=True)
        os.makedirs('output_images', exist_ok=True)
        
        print("\nCreating test image...")
        # Create test image with actual text
        width = 800
        height = 600
        test_image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(test_image)
        
        # Try to use a system font
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            font = ImageFont.load_default()
        
        # Add test dates
        test_dates = [
            "Monday 12th February",
            "Tuesday 13th February",
            "Wednesday 14th February",
            "Thursday 15th February",
            "Friday 16th February",
            "Saturday 17th February",
            "Sunday 18th February"
        ]
        
        y = 50
        for date in test_dates:
            draw.text((50, y), date, fill='black', font=font)
            y += 50
        
        test_image.save('temp_images/test_menu.png')
        print("Test image created successfully")
        
        print("\nTesting date extraction...")
        dates = extract_dates_from_image('temp_images/test_menu.png')
        print(f"Extracted dates: {dates}")
        
        if dates:
            print("\nTesting menu merging...")
            result = add_dates_to_menu(
                'templates/menu_template.pdf',
                dates,
                'output_images/merged_menu.pdf'
            )
            print(f"Menu merge result: {result}")
        
        print("\nTesting header merging...")
        merged_path = merge_header_with_template(
            'temp_images/test_menu.png',
            'templates/template.png'
        )
        print(f"Header merge result: {merged_path}")
        
    except Exception as e:
        print(f"Test failed: {e}")
        return False
    
    return True

if __name__ == '__main__':
    success = test_menu_processing()
    sys.exit(0 if success else 1) 