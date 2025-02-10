#!/usr/bin/env bash
# Install system dependencies
apt-get update -y
apt-get install -y tesseract-ocr

# Install Python dependencies
pip install -r requirements.txt 