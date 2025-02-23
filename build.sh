#!/usr/bin/env bash
set -e  # Exit on any error

echo "🚀 Starting build process..."

# Install system dependencies
echo "📦 Installing system packages..."
echo "Current directory: $(pwd)"
echo "Contents of packages.txt:"
cat packages.txt

echo "Running apt-get update..."
apt-get update -y || {
    echo "Failed to update package list"
    exit 1
}

echo "Installing packages..."
apt-get install -y $(cat packages.txt) || {
    echo "Failed to install packages"
    exit 1
}

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
    apt-get install -y tesseract-ocr tesseract-ocr-eng || {
        echo "Manual installation failed!"
        exit 1
    }
    if ! command -v tesseract &> /dev/null; then
        echo "Manual installation completed but tesseract still not found!"
        exit 1
    fi
fi

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