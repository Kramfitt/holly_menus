#!/usr/bin/env bash
set -e  # Exit on any error

echo "🚀 Starting build process..."

# Check if we're on Render
if [ -n "$RENDER" ] || [ -d "/app" ]; then
    echo "📦 Running on Render - installing system dependencies..."
    
    # Create .apt directory structure
    mkdir -p /app/.apt
    
    # Download and extract packages directly
    echo "📥 Downloading packages..."
    curl -s https://packagecloud.io/github/git-lfs/gpgkey | gpg --dearmor > /etc/apt/trusted.gpg.d/packagecloud.gpg
    
    # Add Tesseract repository
    echo "deb http://deb.debian.org/debian bullseye main" > /etc/apt/sources.list.d/debian.list
    
    # Install packages into .apt directory
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libtesseract-dev \
        libleptonica-dev \
        poppler-utils \
        -o Dir::Cache::Archives="/app/.apt/cache"
    
    # Set up Tesseract paths for the .apt directory
    export TESSDATA_PREFIX="/app/.apt/usr/share/tesseract-ocr/4.00/tessdata"
    export TESSERACT_PATH="/app/.apt/usr/bin/tesseract"
    export LD_LIBRARY_PATH="/app/.apt/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
    
    echo "✅ System packages installed"
    
    # Create symbolic links for Tesseract
    ln -sf /app/.apt/usr/bin/tesseract /usr/local/bin/tesseract
    ln -sf /app/.apt/usr/share/tesseract-ocr /usr/local/share/tesseract-ocr
    
    # Verify Tesseract installation
    echo "🔍 Verifying Tesseract installation..."
    tesseract --version || echo "⚠️ Tesseract version check failed"
    tesseract --list-langs || echo "⚠️ Tesseract languages check failed"
    
    echo "📁 Creating required directories..."
    mkdir -p temp_images output_images menu_templates logs
    chmod 777 temp_images output_images menu_templates logs
    
    echo "📦 Installing Python dependencies..."
    pip install -r requirements.txt
    
    echo "🧪 Testing Tesseract with Python..."
    python -c "
import pytesseract
import os
print('Environment:')
print(f'TESSDATA_PREFIX: {os.getenv(\"TESSDATA_PREFIX\")}')
print(f'TESSERACT_PATH: {os.getenv(\"TESSERACT_PATH\")}')
print(f'Tesseract version: {pytesseract.get_tesseract_version()}')
print(f'Available languages: {pytesseract.get_languages()}')
"
    
    echo "✅ Build completed successfully"
    exit 0
fi

# Rest of the build script for non-Render builds
echo "📊 System Information:"
echo "OS: $(uname -a)"
echo "Distribution: $(cat /etc/os-release | grep PRETTY_NAME || echo 'Unknown')"
echo "Current directory: $(pwd)"
echo "PATH: $PATH"

# Verify system dependencies
echo "📦 Verifying system packages..."

# Verify Tesseract installation
echo "🔍 Verifying Tesseract installation..."
echo "Checking Tesseract binary..."

# Check multiple possible locations
TESSERACT_LOCATIONS=(
    "/usr/bin/tesseract"
    "/usr/local/bin/tesseract"
    "/opt/tesseract/bin/tesseract"
    "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
)

TESSERACT_FOUND=false
for loc in "${TESSERACT_LOCATIONS[@]}"; do
    if [ -f "$loc" ]; then
        echo "✅ Found Tesseract at: $loc"
        TESSERACT_FOUND=true
        export PATH="$(dirname $loc):$PATH"
        break
    fi
done

if [ "$TESSERACT_FOUND" = false ]; then
    echo "❌ Tesseract not found in common locations"
    echo "Please install Tesseract OCR first"
    exit 1
fi

# Create required directories
echo "📁 Creating required directories..."
mkdir -p temp_images output_images menu_templates logs
chmod 777 temp_images output_images menu_templates logs

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Test Tesseract with Python
echo "🧪 Testing Tesseract with Python..."
python -c "
import pytesseract
import os
print('Tesseract version:', pytesseract.get_tesseract_version())
print('Available languages:', pytesseract.get_languages())
"

echo "✅ Build completed successfully" 