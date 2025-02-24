import os
import sys
import pytesseract
from PIL import Image
import numpy as np

def test_tesseract():
    print('🔍 Testing Tesseract configuration...')
    
    # Check environment and configuration
    print(f'Environment:')
    print(f'TESSERACT_PATH: {os.getenv("TESSERACT_PATH")}')
    print(f'TESSDATA_PREFIX: {os.getenv("TESSDATA_PREFIX")}')
    print(f'LD_LIBRARY_PATH: {os.getenv("LD_LIBRARY_PATH")}')
    
    try:
        # Check Tesseract version
        version = pytesseract.get_tesseract_version()
        print(f'✅ Tesseract version: {version}')
        
        # Check available languages
        langs = pytesseract.get_languages()
        print(f'✅ Available languages: {langs}')
        
        # Create test image with text
        print('\n📝 Creating test image...')
        img = Image.new('RGB', (200, 50), color='white')
        img_array = np.array(img)
        
        # Test OCR
        print('🔄 Running OCR test...')
        text = pytesseract.image_to_string(
            img_array,
            config='--psm 6'  # Assume uniform block of text
        )
        print('✅ OCR Test successful')
        return True
        
    except Exception as e:
        print(f'❌ Test failed: {str(e)}')
        print('\nDebug information:')
        print(f'Current directory: {os.getcwd()}')
        print(f'Directory contents: {os.listdir()}')
        print(f'PATH: {os.environ.get("PATH")}')
        return False

if __name__ == '__main__':
    success = test_tesseract()
    sys.exit(0 if success else 1) 