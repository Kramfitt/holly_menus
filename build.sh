#!/usr/bin/env bash

echo "Starting build process..."

# Update package list
sudo apt-get update -y

# Install Tesseract and its dependencies
sudo apt-get install -y tesseract-ocr
sudo apt-get install -y libtesseract-dev

# Debug: Show Tesseract location and version
echo "Tesseract location:"
sudo which tesseract
echo "Tesseract version:"
sudo tesseract --version

# Create symbolic link if needed
sudo ln -s /usr/bin/tesseract /usr/local/bin/tesseract

# Verify link
ls -la /usr/local/bin/tesseract

# Install Python dependencies
pip install -r requirements.txt

# Final check
echo "Final Tesseract check:"
tesseract --version

echo "Build process completed" 