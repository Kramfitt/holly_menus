#!/usr/bin/env bash
set -e  # Exit on any error

echo "🚀 Starting build process..."

# Install system dependencies
echo "📦 Installing system packages..."
echo "Current directory: $(pwd)"
echo "Contents of packages.txt:"
cat packages.txt

echo "Running apt-get update..."
sudo apt-get update -y

echo "Installing packages..."
sudo apt-get install -y $(cat packages.txt)

# Verify Tesseract installation
echo "🔍 Verifying Tesseract installation..."
echo "Checking Tesseract binary..."
which tesseract || echo "tesseract not in PATH"
echo "Checking common locations..."
ls -l /usr/bin/tesseract* || echo "Not found in /usr/bin"
ls -l /usr/local/bin/tesseract* || echo "Not found in /usr/local/bin"

if ! command -v tesseract &> /dev/null; then
    echo "❌ Tesseract is not installed!"
    echo "Attempting manual installation..."
    sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
    if ! command -v tesseract &> /dev/null; then
        echo "Manual installation failed!"
        exit 1
    fi
fi

echo "Running tesseract version..."
tesseract --version

echo "Checking available languages..."
tesseract --list-langs

# Install Python dependencies
echo "🐍 Installing Python packages..."
pip install -r requirements.txt

# Test Tesseract with Python
echo "🧪 Testing Tesseract with Python..."
python -c "
import pytesseract
print('Python Tesseract path:', pytesseract.get_tesseract_cmd())
print('Tesseract version:', pytesseract.get_tesseract_version())
print('Available languages:', pytesseract.get_languages())
"

echo "🏁 Build process completed" 