#!/usr/bin/env bash

echo "🚀 Starting build process..."

# Update package list
echo "📦 Updating package list..."
apt-get update -y

# Install Tesseract and its dependencies
echo "📥 Installing Tesseract..."
apt-get install -y tesseract-ocr
apt-get install -y libtesseract-dev

# Verify Tesseract installation
echo "🔍 Verifying Tesseract installation..."
TESSERACT_PATH=$(which tesseract)
echo "Tesseract path: $TESSERACT_PATH"

if [ -f "/usr/bin/tesseract" ]; then
    echo "✅ Tesseract found in /usr/bin"
    /usr/bin/tesseract --version
else
    echo "❌ Tesseract not found in /usr/bin"
fi

# Create symbolic links
echo "🔗 Creating symbolic links..."
ln -sf /usr/bin/tesseract /usr/local/bin/tesseract
ln -sf /usr/bin/tesseract /opt/render/project/src/tesseract

# Set permissions
echo "🔒 Setting permissions..."
chmod 755 /usr/bin/tesseract
chmod 755 /usr/local/bin/tesseract
chmod 755 /opt/render/project/src/tesseract

# Install Python dependencies
echo "🐍 Installing Python packages..."
pip install -r requirements.txt

# Final verification
echo "✨ Final verification..."
tesseract --version || echo "❌ Tesseract not accessible in PATH"
/usr/bin/tesseract --version || echo "❌ Tesseract not accessible in /usr/bin"
/usr/local/bin/tesseract --version || echo "❌ Tesseract not accessible in /usr/local/bin"

echo "🏁 Build process completed" 