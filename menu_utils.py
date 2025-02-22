from typing import Dict
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
import tempfile
import logging

logger = logging.getLogger(__name__)

def add_dates_to_menu(master_path: str, dates: Dict[str, str], output_path: str) -> bool:
    """
    Add dates to the master menu template.
    
    Args:
        master_path: Path to the master menu PDF template
        dates: Dictionary mapping days to dates (e.g., {'Mon': '3rd March'})
        output_path: Where to save the resulting PDF
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create a temporary PDF for the dates overlay
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            # Create the canvas
            c = canvas.Canvas(temp_file.name, pagesize=letter)
            
            # Define positions for each day's date
            # These will need to be calibrated to your exact template
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
            
            # Merge the overlay with the master template
            master = PdfReader(open(master_path, 'rb'))
            overlay = PdfReader(open(temp_file.name, 'rb'))
            
            output = PdfWriter()
            
            # Merge first pages
            page = master.pages[0]
            page.merge_page(overlay.pages[0])
            output.add_page(page)
            
            # Add any remaining pages from master
            for page in master.pages[1:]:
                output.add_page(page)
            
            # Save the result
            with open(output_path, 'wb') as output_file:
                output.write(output_file)
                
        return True
        
    except Exception as e:
        logger.error(f"Error adding dates to menu: {e}")
        return False
    finally:
        # Clean up temp file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name) 