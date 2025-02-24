from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from PIL import Image
import pytesseract
import io
import re
import os

app = Flask(__name__)
CORS(app)

# Configuration
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB limit
MAX_IMAGE_DIMENSION = 2400  # Maximum width or height

def optimize_image(image):
    """Optimize image for OCR processing"""
    # Convert to RGB if needed
    if image.mode not in ('L', 'RGB'):
        image = image.convert('RGB')
    
    # Resize if too large while maintaining aspect ratio
    if max(image.size) > MAX_IMAGE_DIMENSION:
        ratio = MAX_IMAGE_DIMENSION / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    return image

def find_menu_week(text):
    """Extract menu week pattern from text"""
    pattern = r'(Summer|Winter)\s+Menu\s+Week\s+\d+'
    match = re.search(pattern, text)
    return match.group(0) if match else None

# HTML template for the upload interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Menu Week Detector</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .upload-form {
            margin: 20px 0;
        }
        .result {
            margin-top: 20px;
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
            padding: 15px;
            border-radius: 4px;
            background-color: #f8f9fa;
        }
        .error {
            color: red;
            margin-top: 10px;
        }
        .loading {
            display: none;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Menu Week Detector</h1>
        <p>Upload an image to detect Summer/Winter Menu Week.</p>
        
        <div class="upload-form">
            <form id="uploadForm">
                <input type="file" id="imageFile" accept="image/*" required>
                <button type="submit">Detect Menu Week</button>
            </form>
            <div id="loading" class="loading">Processing...</div>
        </div>
        
        <div id="result" class="result"></div>
        <div id="error" class="error"></div>
    </div>

    <script>
        document.getElementById('uploadForm').onsubmit = async (e) => {
            e.preventDefault();
            const resultDiv = document.getElementById('result');
            const errorDiv = document.getElementById('error');
            const loadingDiv = document.getElementById('loading');
            const fileInput = document.getElementById('imageFile');
            
            resultDiv.textContent = '';
            errorDiv.textContent = '';
            
            if (!fileInput.files.length) {
                errorDiv.textContent = 'Please select an image file.';
                return;
            }

            const formData = new FormData();
            formData.append('image', fileInput.files[0]);
            
            loadingDiv.style.display = 'block';
            
            try {
                const response = await fetch('/ocr', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    if (data.menu_week) {
                        resultDiv.textContent = data.menu_week;
                    } else {
                        errorDiv.textContent = 'No menu week pattern found in the image.';
                    }
                } else {
                    errorDiv.textContent = data.error || 'An error occurred during processing.';
                }
            } catch (error) {
                errorDiv.textContent = 'An error occurred while uploading the image.';
            } finally {
                loadingDiv.style.display = 'none';
            }
        };
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ocr', methods=['POST'])
def ocr():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    
    if not file.filename:
        return jsonify({'error': 'No selected file'}), 400

    # Check file size
    file_content = file.read()
    if len(file_content) > MAX_IMAGE_SIZE:
        return jsonify({'error': 'File size must be less than 5MB'}), 400
    
    # Reset file pointer
    file_stream = io.BytesIO(file_content)
        
    # Check file extension
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}
    if '.' not in file.filename or \
       file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Please upload an image file.'}), 400

    try:
        # Read the image
        image = Image.open(file_stream)
        
        # Convert to RGB if necessary
        if image.mode not in ('L', 'RGB'):
            image = image.convert('RGB')
            
        # Extract text with specific configuration for text detection
        text = pytesseract.image_to_string(
            image,
            config='--psm 6'  # Assume uniform block of text
        )
        
        # Find menu week pattern
        menu_week = find_menu_week(text)
        
        if menu_week:
            return jsonify({'menu_week': menu_week})
        else:
            return jsonify({'error': 'No menu week pattern found in the image.'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Error processing image: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
