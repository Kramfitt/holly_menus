import os
import sys
import platform
import shutil
from typing import Optional
import pytesseract
from PIL import Image, ImageEnhance
import logging

logger = logging.getLogger(__name__)

def get_tesseract_path() -> Optional[str]:
    """Get the appropriate Tesseract path for the current environment"""
    # First check environment variable
    tesseract_path = os.getenv('TESSERACT_PATH')
    if tesseract_path and os.path.exists(tesseract_path):
        return tesseract_path

    # Check if we're on Render
    if os.path.exists('/app/.apt/usr/bin/tesseract'):
        return '/app/.apt/usr/bin/tesseract'

    # Check common installation paths
    common_paths = [
        'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',  # Windows
        '/usr/bin/tesseract',  # Linux
        '/usr/local/bin/tesseract',  # Alternative Linux
        '/opt/homebrew/bin/tesseract',  # macOS
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
            
    # Last resort: check PATH
    return shutil.which('tesseract')

def configure_tesseract() -> bool:
    """Configure Tesseract OCR with the correct binary path"""
    try:
        tesseract_path = get_tesseract_path()
        
        if not tesseract_path:
            logger.error("Tesseract binary not found in any standard location")
            return False
            
        # Set the Tesseract command
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        # Set TESSDATA_PREFIX if not already set
        if not os.getenv('TESSDATA_PREFIX'):
            tessdata_prefix = None
            
            # Check Render-specific path
            render_tessdata = '/app/.apt/usr/share/tesseract-ocr/4.00/tessdata'
            if os.path.exists(render_tessdata):
                tessdata_prefix = render_tessdata
            else:
                # Try to find tessdata relative to binary
                binary_dir = os.path.dirname(tesseract_path)
                possible_paths = [
                    os.path.join(binary_dir, '..', 'share', 'tessdata'),
                    os.path.join(binary_dir, '..', 'share', 'tesseract-ocr', 'tessdata'),
                    '/usr/share/tesseract-ocr/4.00/tessdata',  # Common Linux path
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        tessdata_prefix = path
                        break
            
            if tessdata_prefix:
                os.environ['TESSDATA_PREFIX'] = tessdata_prefix
                logger.info(f"Set TESSDATA_PREFIX to {tessdata_prefix}")
        
        # Verify installation
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages()
        
        logger.info(f"Tesseract configured successfully:")
        logger.info(f"- Path: {tesseract_path}")
        logger.info(f"- TESSDATA_PREFIX: {os.getenv('TESSDATA_PREFIX', 'Not set')}")
        logger.info(f"- Version: {version}")
        logger.info(f"- Languages: {langs}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure Tesseract: {str(e)}")
        return False

def optimize_image_for_ocr(image: Image.Image) -> Image.Image:
    """Optimize image for better OCR results"""
    try:
        # Convert to RGB if needed
        if image.mode not in ('L', 'RGB'):
            image = image.convert('RGB')
        
        # Resize if too large (max dimension 2400px)
        max_dimension = 2400
        if max(image.size) > max_dimension:
            ratio = max_dimension / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Enhance image for OCR
        image = ImageEnhance.Contrast(image).enhance(1.5)
        image = ImageEnhance.Sharpness(image).enhance(1.5)
        
        # Convert to grayscale for OCR
        image = image.convert('L')
        
        return image
        
    except Exception as e:
        logger.error(f"Failed to optimize image: {str(e)}")
        return image  # Return original image if optimization fails

def perform_ocr(image: Image.Image, config: Optional[str] = None) -> str:
    """Perform OCR on an image with optimized settings"""
    try:
        # Optimize image
        optimized = optimize_image_for_ocr(image)
        
        # Use custom OCR config for better results
        custom_config = config or '--psm 6 --oem 1'
        
        # Perform OCR
        text = pytesseract.image_to_string(optimized, config=custom_config)
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"OCR failed: {str(e)}")
        return "" 