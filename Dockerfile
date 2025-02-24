# Use Python 3.11 slim base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata \
    TESSERACT_PATH=/usr/bin/tesseract \
    LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && tesseract --version \
    && tesseract --list-langs \
    && echo "Tesseract installation verified"

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Verify Tesseract installation and Python integration
RUN echo "Verifying Tesseract installation..." \
    && python -c "import pytesseract; print(f'Tesseract Version: {pytesseract.get_tesseract_version()}')" \
    && python test_tesseract.py

# Expose port
EXPOSE 5000

# Start command
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"] 