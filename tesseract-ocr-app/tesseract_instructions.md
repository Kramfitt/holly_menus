# Setting up Tesseract OCR on Render

This guide provides detailed instructions for setting up a Python web application with Tesseract OCR on Render.com.

## Required Files

### 1. Dockerfile
```dockerfile
# Use the official Python image as the base
FROM python:3.9-slim

# Install Tesseract OCR and required system dependencies
RUN apt-get update && \
    apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    # Optional: Install specific language packs if needed
    # tesseract-ocr-eng \
    # tesseract-ocr-fra \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Run the application with Gunicorn
CMD ["gunicorn", "--workers", "2", "--timeout", "120", "--threads", "2", "--worker-class", "gthread", "--bind", "0.0.0.0:5000", "app:app"]
```

### 2. requirements.txt
```
Flask==3.1.0
pytesseract==0.3.13
Pillow==11.1.0
gunicorn==21.2.0
Flask-CORS==4.0.0
```

### 3. render.yaml (Optional but recommended)
```yaml
services:
  - type: web
    name: your-app-name
    env: docker
    buildCommand: docker build -t your-app-name .
    startCommand: docker run -p 5000:5000 your-app-name
    envVars:
      - key: PYTHON_VERSION
        value: 3.9.0
    healthCheckPath: /
    autoDeploy: true
    plan: starter # Recommended for OCR processing
```

## Deployment Steps

1. **Prepare Your Repository**
   - Ensure all the above files are in your repository
   - The Dockerfile must be in the root directory
   - Make sure your application code uses the correct port (5000)

2. **Render.com Setup**
   - Create a new Web Service in Render
   - Connect your GitHub repository
   - Select "Docker" as the environment
   - The rest should be automatic due to the Dockerfile

## Important Notes

### Memory and Processing
- OCR is memory-intensive
- Use the starter plan or higher on Render
- Configure Gunicorn workers based on available memory
- Consider image size limits in your application

### Tesseract Configuration
- Default installation includes English language
- Additional languages need explicit installation
- Configure Tesseract parameters in your code:
```python
# Example configuration in your Python code
text = pytesseract.image_to_string(
    image,
    config='--psm 6'  # Page Segmentation Mode
)
```

### Error Handling
Common issues and solutions:
1. **Tesseract not found**
   - Ensure Dockerfile installs tesseract-ocr
   - Check if tesseract is in PATH
   
2. **Memory errors**
   - Reduce image size before processing
   - Limit concurrent processing
   - Use appropriate Render plan

3. **Timeout issues**
   - Increase Gunicorn timeout
   - Optimize image processing
   - Add proper error handling

### Example Image Processing Code
```python
def optimize_image(image):
    """Optimize image for OCR processing"""
    # Convert to RGB if needed
    if image.mode not in ('L', 'RGB'):
        image = image.convert('RGB')
    
    # Resize if too large
    max_dimension = 2400
    if max(image.size) > max_dimension:
        ratio = max_dimension / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    return image

def process_image(file_stream):
    try:
        image = Image.open(file_stream)
        image = optimize_image(image)
        text = pytesseract.image_to_string(
            image,
            config='--psm 6'
        )
        return text
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None
```

### Testing
Before deploying:
1. Test locally with Docker:
```bash
docker build -t your-app-name .
docker run -p 5000:5000 your-app-name
```

2. Test different image types and sizes
3. Monitor memory usage
4. Check processing times

### Monitoring and Maintenance
- Use Render's logging to monitor application
- Watch for timeout errors
- Monitor memory usage
- Keep dependencies updated

## Troubleshooting

### Common Issues

1. **Build Failures**
   - Check Dockerfile syntax
   - Verify all required files are present
   - Check build logs for specific errors

2. **Runtime Errors**
   - Verify Tesseract installation in container
   - Check memory usage
   - Monitor application logs

3. **Performance Issues**
   - Optimize image processing
   - Adjust worker configuration
   - Consider upgrading Render plan

### Verification Steps

After deployment:
1. Test with small images first
2. Gradually test larger images
3. Monitor response times
4. Check error rates

## Security Considerations

1. **File Uploads**
   - Validate file types
   - Limit file sizes
   - Sanitize file names

2. **API Security**
   - Implement rate limiting
   - Add authentication if needed
   - Validate input data

## Optimization Tips

1. **Image Processing**
   - Resize large images
   - Convert to appropriate format
   - Optimize for OCR

2. **Application Performance**
   - Cache results if possible
   - Implement request queuing
   - Add error recovery

3. **Resource Usage**
   - Monitor memory usage
   - Adjust worker configuration
   - Implement timeouts

## Support and Resources

- [Tesseract Documentation](https://github.com/tesseract-ocr/tesseract)
- [Python-Tesseract](https://github.com/madmaze/python-tesseract)
- [Render Documentation](https://render.com/docs)
- [Docker Documentation](https://docs.docker.com) 