from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os

def create_template_pdf():
    """Create a template PDF with placeholders for dates"""
    # Ensure templates directory exists
    os.makedirs('templates', exist_ok=True)
    
    # Create PDF
    c = canvas.Canvas('templates/menu_template.pdf', pagesize=letter)
    
    # Add some guide text
    c.drawString(100, 700, "Monday:")
    c.drawString(200, 700, "Tuesday:")
    c.drawString(300, 700, "Wednesday:")
    c.drawString(400, 700, "Thursday:")
    c.drawString(500, 700, "Friday:")
    c.drawString(600, 700, "Saturday:")
    c.drawString(700, 700, "Sunday:")
    
    # Add some lines
    for y in range(650, 100, -50):
        c.line(50, y, 750, y)
    
    c.save()
    print("Created template PDF at templates/menu_template.pdf")

if __name__ == '__main__':
    create_template_pdf() 