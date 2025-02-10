#!/usr/bin/env bash

# Debug: Print current directory and contents
pwd
ls -la

# Update package list
apt-get update -y

# Install Tesseract and its dependencies
apt-get install -y tesseract-ocr
apt-get install -y libtesseract-dev

# Verify Tesseract installation
tesseract --version
which tesseract

# Add Tesseract to PATH if needed
export PATH=$PATH:/usr/bin/tesseract

# Install Python dependencies
pip install -r requirements.txt

# Debug: Final PATH
echo "Final PATH: $PATH" 