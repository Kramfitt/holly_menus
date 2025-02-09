from PIL import Image, ImageDraw, ImageFont
import datetime
import re
import os
import sys
from datetime import datetime, timedelta
import tempfile
from pdf2image import convert_from_path

# Load the template image
def generate_menu_image(template_path, output_path, start_date):
    """
    Replaces placeholders in the image with actual dates
    starting from the given start_date.
    """
    try:
        # Print current directory and file check
        print(f"Current directory: {os.getcwd()}", file=sys.stderr)
        print(f"Looking for template: {template_path}", file=sys.stderr)
        
        if not os.path.exists(template_path):
            print(f"Error: Template file not found: {template_path}", file=sys.stderr)
            return
            
        # Open the template image
        img = Image.open(template_path)
        draw = ImageDraw.Draw(img)

        # Load font from project directory with fallbacks
        font_paths = [
            os.path.join(os.path.dirname(__file__), 'fonts', 'Roboto-Regular.ttf'),
            os.path.join(os.path.dirname(__file__), 'fonts', 'DejaVuSans.ttf'),
            'arial.ttf'  # System font as last resort
        ]
        
        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, 36)
                print(f"Using font: {font_path}", file=sys.stderr)
                break
            except Exception as e:
                print(f"Could not load font {font_path}: {e}", file=sys.stderr)
        
        if font is None:
            print("Warning: Using default font", file=sys.stderr)
            font = ImageFont.load_default()

        # Calculate the dates for the week
        base_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")  # Convert string to datetime
        date_replacements = {f"{{DATE-{i+1}}}": (base_date + datetime.timedelta(days=i)).strftime("%a %d %b") for i in range(7)}

        # Define coordinates for date placements (manually set based on the template)
        date_positions = {
            "{{DATE-1}}": (6000, 100),
            "{{DATE-2}}": (3000, 100),
            "{{DATE-3}}": (5000, 100),
            "{{DATE-4}}": (7000, 100),
            "{{DATE-5}}": (9000, 100),
            "{{DATE-6}}": (11000, 100),
            "{{DATE-7}}": (13000, 100),

        }

        # Replace placeholders with actual dates
        for placeholder, date_text in date_replacements.items():
            if placeholder in date_positions:
                position = date_positions[placeholder]
                draw.text(position, date_text, fill="white", font=font)

        # Save the output image
        img.save(output_path)
        print(f"Updated menu image saved as {output_path}")
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        raise

# Example usage
if __name__ == "__main__":
    # Use the correct path to your template
    template_path = "templates/summer/week3_png"  # or your actual template path
    output_path = "output/menu_with_dates.png"
    start_date = "2025-02-10"
    
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    
    # Generate menu
    generate_menu_image(template_path, output_path, start_date)

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

def merge_menu_parts(input_image, menu_details):
    """Add dates to an image"""
    try:
        # Open the image directly (no PDF conversion needed)
        image = Image.open(input_image)
        
        # Create drawing context
        draw = ImageDraw.Draw(image)
        
        # Load font with fallbacks
        font = None
        font_paths = [
            os.path.join(os.path.dirname(__file__), 'fonts', 'Roboto-Regular.ttf'),
            'arial.ttf',  # System font
            None  # Will use default if others fail
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
        
        # Define coordinates for date placements
        date_positions = {
            "{{DATE-1}}": (320, 190),
            "{{DATE-2}}": (600, 190),
            "{{DATE-3}}": (850, 190),
            "{{DATE-4}}": (1150, 190),
            "{{DATE-5}}": (1450, 190),
            "{{DATE-6}}": (1700, 190),
            "{{DATE-7}}": (1985, 190),
        }
        
        # Add dates using the defined positions
        start_date = menu_details['start_date']
        for i in range(7):
            marker = f"{{{{DATE-{i+1}}}}}"
            if marker in date_positions:
                pos = date_positions[marker]
                current_date = start_date + timedelta(days=i)
                date_text = current_date.strftime('%a %d\n%b')
                
                # Get text size for background
                bbox = draw.textbbox(pos, date_text, font=font)
                padding = 10  # Increased padding
                
                # Draw white background rectangle
                background_bbox = (
                    bbox[0] - padding,
                    bbox[1] - padding,
                    bbox[2] + padding,
                    bbox[3] + padding
                )
                draw.rectangle(background_bbox, fill='white')
                
                # Draw text in black
                draw.text(pos, date_text, fill='black', font=font)
        
        # Save and return path
        output_path = os.path.join(tempfile.mkdtemp(), "menu_with_dates.png")
        image.save(output_path)
        return output_path
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        raise

if __name__ == "__main__":
    test_image_modification()
