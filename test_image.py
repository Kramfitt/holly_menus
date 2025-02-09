from PIL import Image, ImageDraw, ImageFont
import datetime
import re
import os
import sys
from datetime import datetime, timedelta
import tempfile
import pytesseract

def detect_orientation(image):
    """
    Detect the orientation of an image using pytesseract OSD.
    Returns: angle of rotation (0, 90, 180, 270)
    """
    try:
        osd_data = pytesseract.image_to_osd(image)
        rotation_angle = int(osd_data.split("Rotate:")[1].split("\n")[0].strip())
        print(f"Detected rotation: {rotation_angle}°", file=sys.stderr)
        return rotation_angle
    except Exception as e:
        print(f"Error detecting orientation: {e}", file=sys.stderr)
        return 0

def find_top_left(image):
    """Find the top-left corner using OCR bounding boxes"""
    try:
        # Get OCR data with bounding boxes
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        # Find the topmost, leftmost text bounding box
        min_x = float('inf')
        min_y = float('inf')
        
        for i in range(len(data['text'])):
            if data['conf'][i] > 0:  # Only consider confident detections
                x = data['left'][i]
                y = data['top'][i]
                
                if x < min_x or (x == min_x and y < min_y):
                    min_x = x
                    min_y = y
        
        print(f"Found top-left corner at: ({min_x}, {min_y})", file=sys.stderr)
        return min_x, min_y
        
    except Exception as e:
        print(f"Error finding top-left: {str(e)}", file=sys.stderr)
        raise

def merge_menu_parts(input_image, menu_details):
    """Add dates to an image using detected top-left reference"""
    try:
        # Open and normalize image orientation
        image = Image.open(input_image)
        
        # Detect and correct orientation
        rotation_angle = detect_orientation(image)
        if rotation_angle in [90, 180, 270]:
            image = image.rotate(360 - rotation_angle, expand=True)
            print(f"Rotated image by {360 - rotation_angle}°", file=sys.stderr)
        
        # Get dimensions and find top-left corner
        width, height = image.size
        print(f"Image dimensions after rotation: {width}x{height}", file=sys.stderr)
        
        top_left_x, top_left_y = find_top_left(image)
        
        # Create drawing context
        draw = ImageDraw.Draw(image)
        
        # Load font with fallbacks
        font = None
        font_paths = [
            os.path.join(os.path.dirname(__file__), 'fonts', 'Roboto-Regular.ttf'),
            'arial.ttf',
            None
        ]
        
        for font_path in font_paths:
            try:
                if font_path is None:
                    font = ImageFont.load_default()
                else:
                    font = ImageFont.truetype(font_path, 36)
                print(f"Using font: {font_path}", file=sys.stderr)
                break
            except Exception as e:
                print(f"Could not load font {font_path}: {e}", file=sys.stderr)
                continue
        
        # Define offsets from detected top-left (x, y)
        x_spacing = 280  # Horizontal spacing between dates
        #y_offset = 160 or 80   # Vertical offset from top

        date_offsets = [
            (180 + top_left_x + (x_spacing * i), top_left_y + 80)
            for i in range(7)
        ]
        
        # Add dates using offsets
        start_date = menu_details['start_date']
        for i, offset in enumerate(date_offsets):
            current_date = start_date + timedelta(days=i)
            date_text = current_date.strftime('%a %d\n%b')
            
            # Get text size for background
            bbox = draw.textbbox(offset, date_text, font=font)
            padding = 10
            
            # Draw white background rectangle
            background_bbox = (
                bbox[0] - padding,
                bbox[1] - padding,
                bbox[2] + padding,
                bbox[3] + padding
            )
            draw.rectangle(background_bbox, fill='white')
            
            # Draw text in black
            draw.text(offset, date_text, fill='black', font=font)
            print(f"Added date at offset {offset}", file=sys.stderr)
        
        # Save and return path
        output_path = os.path.join(tempfile.mkdtemp(), "menu_with_dates.png")
        image.save(output_path)
        return output_path
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        raise

def test_image_modification():
    try:
        print("Testing image modification...")
        
        # Test menu details
        menu_details = {
            'start_date': datetime.now() + timedelta(days=14),
            'season': 'Summer',
            'week_number': 1
        }
        
        # Input and output paths
        input_pdf = "templates/summer/week3_template.png"  # Updated path
        
        print(f"Processing PDF: {input_pdf}")
        print(f"Start date: {menu_details['start_date'].strftime('%B %d, %Y')}")
        
        # Convert and modify
        output_path = merge_menu_parts(input_pdf, menu_details)
        
        print(f"Modified image saved to: {output_path}")
        print("Test completed!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    test_image_modification()