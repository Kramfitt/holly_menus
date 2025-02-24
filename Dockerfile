# Use Python 3.11 slim base image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set up Tesseract environment
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
ENV TESSERACT_PATH=/usr/bin/tesseract
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu

# Create test script to verify Tesseract
RUN echo 'import pytesseract; print(pytesseract.get_tesseract_version())' > test_tesseract.py \
    && python test_tesseract.py

# Expose port
EXPOSE 5000

# Start command
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"] 