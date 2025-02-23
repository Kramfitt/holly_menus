# Use Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies and Tesseract
RUN apt-get update && \
    apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && which tesseract \
    && tesseract --version \
    && tesseract --list-langs

# Set Tesseract path after verifying installation
ENV TESSERACT_PATH=/usr/bin/tesseract

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Final verification of Tesseract
RUN echo "Verifying Tesseract installation..." && \
    if [ ! -f "$TESSERACT_PATH" ]; then \
        echo "Tesseract not found at $TESSERACT_PATH" && \
        exit 1; \
    fi && \
    $TESSERACT_PATH --version && \
    echo "Tesseract verification complete"

# Default command
CMD ["gunicorn", "app:app"] 