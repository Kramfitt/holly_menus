import os
import sys
import subprocess
from PIL import Image
import numpy as np
import pytesseract

def check_tesseract():
    print("\n=== Tesseract Installation Check ===\n")
    
    # Check environment variable
    tesseract_path = os.getenv('TESSERACT_PATH', 'Not set')
    print(f"TESSERACT_PATH env var: {tesseract_path}")
    
    # Check pytesseract path
    print(f"pytesseract command: {pytesseract.get_tesseract_cmd()}")
    
    # Check binary location
    try:
        result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
        print(f"Binary location: {result.stdout.strip() if result.stdout else 'Not found'}")
    except Exception as e:
        print(f"Error checking binary: {e}")
    
    # Check version
    try:
        version = pytesseract.get_tesseract_version()
        print(f"Tesseract version: {version}")
    except Exception as e:
        print(f"Error getting version: {e}")
    
    # Check languages
    try:
        langs = pytesseract.get_languages()
        print(f"Available languages: {langs}")
    except Exception as e:
        print(f"Error getting languages: {e}")
    
    # Test OCR
    print("\nTesting OCR functionality:")
    try:
        # Create a test image with text
        img = Image.new('RGB', (200, 50), color='white')
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        d.text((10,10), "Testing 123", fill='black')
        
        # Try OCR
        text = pytesseract.image_to_string(img)
        print(f"OCR Test result: {text.strip()}")
        print("✅ OCR test successful")
    except Exception as e:
        print(f"❌ OCR test failed: {e}")
    
    print("\n=== End of Test ===")

if __name__ == "__main__":
    check_tesseract() 