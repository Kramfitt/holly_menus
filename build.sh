#!/usr/bin/env bash
set -e  # Exit on any error

echo "🚀 Starting build process..."

# Check if we're building for Docker
if [ -n "$DOCKER_BUILD" ] || [ -f "Dockerfile.web" ] || [ -f "Dockerfile.worker" ]; then
    echo "🐳 Docker build detected - skipping system checks"
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
    echo "🏁 Build process completed"
    exit 0
fi

# Rest of the build script for non-Docker builds
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
    echo "Checking PATH for tesseract..."
    which tesseract || {
        echo "❌ Tesseract not found in PATH"
        echo "Available files in /usr/bin:"
        ls -la /usr/bin/tesseract* || echo "No Tesseract files found in /usr/bin"
        echo "Available files in /usr/local/bin:"
        ls -la /usr/local/bin/tesseract* || echo "No Tesseract files found in /usr/local/bin"
        exit 1
    }
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

# Verify Poppler installation
echo "📄 Verifying Poppler installation..."
which pdftoppm || {
    echo "❌ Poppler (pdftoppm) not found"
    echo "Available files in /usr/bin:"
    ls -la /usr/bin/pdf* || echo "No PDF tools found in /usr/bin"
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
import os
import pytesseract
print('Environment TESSERACT_PATH:', os.getenv('TESSERACT_PATH'))
print('Python Tesseract path:', pytesseract.get_tesseract_cmd())
print('Tesseract version:', pytesseract.get_tesseract_version())
print('Available languages:', pytesseract.get_languages())
" || {
    echo "Failed to test Tesseract with Python"
    exit 1
}

echo "🏁 Build process completed" 