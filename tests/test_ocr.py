import os
import sys
import pytest
from PIL import Image
from app.utils.tesseract_config import configure_tesseract, perform_ocr
from app.utils.template_generator import create_template_pdf, create_test_image

def test_tesseract_configuration():
    """Test Tesseract configuration"""
    assert configure_tesseract(), "Tesseract configuration failed"

def test_template_generation():
    """Test template generation"""
    # Create template PDF
    template_path = create_template_pdf()
    assert template_path is not None, "Failed to create template PDF"
    assert os.path.exists(template_path), f"Template PDF not found at {template_path}"
    
    # Create test image
    test_image_path = create_test_image()
    assert test_image_path is not None, "Failed to create test image"
    assert os.path.exists(test_image_path), f"Test image not found at {test_image_path}"
    
    return test_image_path

def test_ocr_extraction():
    """Test OCR date extraction"""
    # Create test image
    test_image_path = test_template_generation()
    
    # Perform OCR
    with Image.open(test_image_path) as img:
        text = perform_ocr(img)
        
    # Verify extracted text
    assert text, "No text extracted from image"
    assert "Monday" in text, "Failed to extract 'Monday' from image"
    assert "February" in text, "Failed to extract 'February' from image"
    
    # Check for specific date format
    lines = text.split('\n')
    for line in lines:
        if line.strip():
            assert any(day in line for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']), \
                f"Line does not contain a day of the week: {line}"
            assert "February" in line, f"Line does not contain month: {line}"

if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v']) 