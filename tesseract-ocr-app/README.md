# Tesseract OCR Test Project

This project contains test scripts for validating Tesseract OCR functionality, specifically for menu date extraction and processing.

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure Tesseract is installed and accessible in your PATH
3. Set the TESSDATA_PREFIX environment variable to point to your Tesseract data directory

## Project Structure

- `test_menu_merge.py`: Main test script for OCR and menu processing
- `create_test_image.py`: Creates a test image with sample dates
- `create_template.py`: Creates a template image for testing header merging
- `templates/`: Directory containing template files
- `temp_images/`: Directory for temporary image files
- `output_images/`: Directory for processed output files

## Running Tests

1. Generate test data:
```bash
python create_template.py
python create_test_image.py
```

2. Run the test script:
```bash
python test_menu_merge.py
```

The test script will:
- Extract dates from the test image using OCR
- Merge dates with a template
- Process header images
- Save results in the output_images directory

## Debugging

If OCR is not working:
1. Check Tesseract installation: `tesseract --version`
2. Verify TESSDATA_PREFIX is set correctly
3. Check the test image is generated properly
4. Review debug output in the console

## Files

- `test_data.txt`: Sample dates for testing
- `test_menu.png`: Generated test image with dates
- `template.png`: Template image for testing header merging 