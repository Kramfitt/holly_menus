#!/usr/bin/env bash
set -e  # Exit on any error

echo "🚀 Starting build process..."

# Verify system dependencies
echo "📦 Verifying system packages..."
echo "Current directory: $(pwd)"

# Verify Tesseract installation
echo "🔍 Verifying Tesseract installation..."
echo "Checking Tesseract binary..."
which tesseract || {
    echo "❌ Tesseract not found in PATH"
    exit 1
}

echo "Checking common locations..."
ls -l /usr/bin/tesseract* || echo "Not found in /usr/bin"
ls -l /usr/local/bin/tesseract* || echo "Not found in /usr/local/bin"

echo "Running tesseract version..."
tesseract --version || {
    echo "Failed to get tesseract version"
    exit 1
}

echo "Checking available languages..."
tesseract --list-langs || {
    echo "Failed to list languages"
    exit 1
}

# Verify Poppler installation
echo "📄 Verifying Poppler installation..."
which pdftoppm || {
    echo "❌ Poppler (pdftoppm) not found"
    exit 1
}

# Install Python dependencies
echo "🐍 Installing Python packages..."
pip install -r requirements.txt || {
    echo "Failed to install Python packages"
    exit 1
}

# Test Tesseract with Python
echo "🧪 Testing Tesseract with Python..."
python -c "
import pytesseract
print('Python Tesseract path:', pytesseract.get_tesseract_cmd())
print('Tesseract version:', pytesseract.get_tesseract_version())
print('Available languages:', pytesseract.get_languages())
" || {
    echo "Failed to test Tesseract with Python"
    exit 1
}

echo "🏁 Build process completed" 