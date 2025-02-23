import os
import sys
import pytesseract
from PIL import Image
import numpy as np

def test_tesseract():
    print('🔍 Testing Tesseract configuration...')
    
    # Check environment and configuration
    print(f'Environment TESSERACT_PATH: {os.getenv("TESSERACT_PATH")}')
    print(f'Python Tesseract path: {pytesseract.get_tesseract_cmd()}')
    print(f'Tesseract version: {pytesseract.get_tesseract_version()}')
    print(f'Available languages: {pytesseract.get_languages()}')
    
    # Create a test image with text
    print('\n📝 Creating test image...')
    img = Image.new('RGB', (100, 30), color='white')
    img_array = np.array(img)
    
    try:
        # Attempt OCR on the test image
        print('🔄 Running OCR test...')
        text = pytesseract.image_to_string(img_array)
        print('✅ OCR Test successful')
        return True
    except Exception as e:
        print(f'❌ OCR Test failed: {str(e)}')
        return False

if __name__ == '__main__':
    success = test_tesseract()
    sys.exit(0 if success else 1) 