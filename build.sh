#!/usr/bin/env bash

echo "🚀 Starting build process..."

# Install system dependencies
echo "📦 Installing system packages..."
apt-get update -y
apt-get install -y $(cat packages.txt)

# Verify Tesseract installation
echo "🔍 Verifying Tesseract installation..."
if ! command -v tesseract &> /dev/null; then
    echo "❌ Tesseract is not installed!"
    exit 1
fi
tesseract --version
tesseract --list-langs

# Install Python dependencies
echo "🐍 Installing Python packages..."
pip install -r requirements.txt

# Test Tesseract with Python
echo "🧪 Testing Tesseract with Python..."
python -c "
import pytesseract
print('Tesseract version:', pytesseract.get_tesseract_version())
print('Available languages:', pytesseract.get_languages())
"

echo "🏁 Build process completed" 