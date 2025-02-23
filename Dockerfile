# Use Render's pre-built image that includes Tesseract
FROM render/python:3.11

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    TESSERACT_PATH=/usr/bin/tesseract

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Verify Tesseract installation
RUN tesseract --version

# Default command
CMD ["gunicorn", "app:app"] 