# Use the official Python image as the base
FROM python:3.9-slim

# Install Tesseract OCR
RUN apt-get update && apt-get install -y tesseract-ocr

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
ENV PIP_ROOT_USER_ACTION=ignore
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Define the command to run the application
#CMD ["python", "app.py"]
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]