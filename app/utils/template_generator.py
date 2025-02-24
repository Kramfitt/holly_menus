from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image, ImageDraw, ImageFont
import os
import logging

logger = logging.getLogger(__name__)

def create_template_pdf(output_path: str = None) -> str:
    """Create a template PDF with placeholders for dates"""
    try:
        # Use default path if none provided
        if not output_path:
            output_path = os.path.join('menu_templates', 'menu_template.pdf')
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create PDF
        c = canvas.Canvas(output_path, pagesize=letter)
        
        # Add day labels
        c.drawString(100, 700, "Monday:")
        c.drawString(200, 700, "Tuesday:")
        c.drawString(300, 700, "Wednesday:")
        c.drawString(400, 700, "Thursday:")
        c.drawString(500, 700, "Friday:")
        c.drawString(600, 700, "Saturday:")
        c.drawString(700, 700, "Sunday:")
        
        # Add guide lines
        for y in range(650, 100, -50):
            c.line(50, y, 750, y)
        
        c.save()
        logger.info(f"Created template PDF at {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to create template PDF: {e}")
        return None

def create_test_image(dates: list = None, output_path: str = None) -> str:
    """Create a test image with sample dates"""
    try:
        # Use default dates if none provided
        if not dates:
            dates = [
                "Monday 12th February",
                "Tuesday 13th February",
                "Wednesday 14th February",
                "Thursday 15th February",
                "Friday 16th February",
                "Saturday 17th February",
                "Sunday 18th February"
            ]
            
        # Use default path if none provided
        if not output_path:
            output_path = os.path.join('temp_images', 'test_menu.png')
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create image
        width = 800
        height = 600
        image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(image)
        
        # Try to use a system font
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            font = ImageFont.load_default()
        
        # Draw dates
        y = 50
        for date in dates:
            draw.text((50, y), date, fill='black', font=font)
            y += 50
        
        # Save image
        image.save(output_path)
        logger.info(f"Created test image at {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to create test image: {e}")
        return None 