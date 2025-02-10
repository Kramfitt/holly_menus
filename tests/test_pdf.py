import os
import sys
import tempfile
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
import re
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageDraw, ImageFont

def convert_pdf_to_png(pdf_path):
    """Convert PDF to PNG and rotate to normal orientation"""
    try:
        print(f"Converting PDF to PNG: {pdf_path}", file=sys.stderr)
        images = convert_from_path(
            pdf_path,
            poppler_path="C:\\Poppler\\Release-24.08.0-0\\poppler-24.08.0\\Library\\bin"
        )
        
        # Get first page and rotate it
        image = images[0].rotate(90, expand=True)  # Changed from 270° to 90°
        
        # Save rotated PNG
        temp_dir = tempfile.mkdtemp()
        png_path = os.path.join(temp_dir, "menu.png")
        image.save(png_path, "PNG")
        print(f"Saved rotated PNG to: {png_path}", file=sys.stderr)
        
        return png_path
        
    except Exception as e:
        print(f"Error converting PDF: {str(e)}", file=sys.stderr)
        raise

def add_dates_to_image(image_path, menu_details):
    """Add dates to an image using PIL/Pillow"""
    try:
        print(f"Processing: {image_path}", file=sys.stderr)
        
        # Open the image (now already rotated)
        image = Image.open(image_path)
        
        # Print image dimensions
        width, height = image.size
        print(f"\nImage dimensions: {width}x{height}", file=sys.stderr)
        
        # Create drawing context
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            print("Arial not found, using default font", file=sys.stderr)
            font = ImageFont.load_default()
        
        # Calculate dates
        start_date = menu_details['start_date']
        
        # Calculate box width for one date (for spacing)
        sample_date = "Wed 28\nFeb"  # Typical two-line date
        bbox = draw.textbbox((0, 0), sample_date, font=font)
        box_width = bbox[2] - bbox[0] + 10  # Add padding
        print(f"Date box width: {box_width}", file=sys.stderr)
        
        # Calculate positions based on image width
        base_x = 280  # Starting position
        spacing = 290  # Space between dates
        
        positions = [
            (base_x, 145),      # Monday
            (base_x + spacing, 100),  # Tuesday
            (base_x + spacing*2, 100),  # Wednesday
            (base_x + spacing*3, 100),  # Thursday
            (base_x + spacing*4, 100),  # Friday
            (base_x + spacing*5, 100), # Saturday
            (base_x + spacing*6, 100)  # Sunday
        ]
        
        print("\nPositions:", file=sys.stderr)
        for i, pos in enumerate(positions):
            print(f"Day {i+1}: {pos}", file=sys.stderr)
        
        # Add each date
        for i, pos in enumerate(positions):
            current_date = start_date + timedelta(days=i)
            date_line1 = current_date.strftime('%a %d')
            date_line2 = current_date.strftime('%b')
            
            # Add white background for both lines
            text_bbox1 = draw.textbbox(pos, date_line1, font=font)
            text_bbox2 = draw.textbbox((pos[0], pos[1] + 40), date_line2, font=font)
            
            combined_bbox = [
                min(text_bbox1[0], text_bbox2[0]) - 5,
                text_bbox1[1] - 5,
                max(text_bbox1[2], text_bbox2[2]) + 5,
                text_bbox2[3] + 5
            ]
            
            # Draw white background
            draw.rectangle(combined_bbox, fill='white')
            
            # Add date text
            draw.text(pos, date_line1, fill='black', font=font)
            draw.text((pos[0], pos[1] + 40), date_line2, fill='black', font=font)
            
            print(f"Added date {date_line1} {date_line2} at position {pos}", file=sys.stderr)
        
        # Save modified image
        output_path = os.path.join(tempfile.mkdtemp(), "menu_with_dates.png")
        image.save(output_path)
        print(f"Saved to: {output_path}", file=sys.stderr)
        
        return output_path
        
    except Exception as e:
        print(f"Error adding dates: {str(e)}", file=sys.stderr)
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
        
        # Convert PDF to PNG first
        pdf_path = "templates/summer/Summer_Week_1.pdf"
        png_path = convert_pdf_to_png(pdf_path)
        
        print(f"Processing image: {png_path}")
        print(f"Start date: {menu_details['start_date'].strftime('%B %d, %Y')}")
        
        # Modify image
        output_path = add_dates_to_image(png_path, menu_details)
        
        print(f"Modified image saved to: {output_path}")
        print("Test completed!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

def find_date_markers(pdf_path):
    """Find markers in already-rotated PDF"""
    try:
        print(f"Converting PDF to image: {pdf_path}")
        
        # Convert PDF to image with rotation
        images = convert_from_path(
            pdf_path, 
            poppler_path="C:\\Poppler\\Release-24.08.0-0\\poppler-24.08.0\\Library\\bin"
        )
        
        # Rotate image before OCR
        image = images[0].rotate(90, expand=True)
        
        # Get OCR data with positions
        print("\nExtracting text and positions using OCR...")
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        # Look for all date markers
        markers_found = []
        for i, text in enumerate(data['text']):
            for marker_num in range(1, 8):
                curly_marker = f"{{{{DATE-{marker_num}}}}}"
                if curly_marker in text:
                    x, y = data['left'][i], data['top'][i]
                    width, height = data['width'][i], data['height'][i]
                    markers_found.append({
                        'marker': curly_marker,
                        'number': marker_num,
                        'position': (x, y),
                        'size': (width, height)
                    })
        
        # Print results
        print("\nMarkers found:")
        for marker in sorted(markers_found, key=lambda x: x['number']):
            print(f"Marker {marker['number']}:")
            print(f"  Text: {marker['marker']}")
            print(f"  Position: {marker['position']}")
            print(f"  Size: {marker['size']}")
            print()
        
        return markers_found
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

def test_marker_finding():
    # Test with first summer menu
    pdf_path = "templates/summer/Summer_Week_1.pdf"
    return find_date_markers(pdf_path)

if __name__ == "__main__":
    test_image_modification()
    test_marker_finding()