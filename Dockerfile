FROM python:3.9-slim

# Create a non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
# Install as non-root user
RUN pip install --user -r requirements.txt

# Copy the rest of the application
COPY . .

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Make it clear this is a background worker
ENV IS_WORKER=true

CMD ["python", "menu_scheduler.py"]