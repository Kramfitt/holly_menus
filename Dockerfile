FROM python:3.9-slim

# Create a non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Create a test script
RUN echo "print('Hello from test script')" > test.py

# Copy requirements first for better caching
COPY requirements.txt .

# Install packages globally (removing --user flag)
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Make it clear this is a background worker
ENV IS_WORKER=true

# Try running the test script first
CMD ["sh", "-c", "python test.py && python menu_scheduler.py"]