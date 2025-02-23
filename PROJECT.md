# Holly Lodge Menu System - Technical Documentation

## System Overview
Automated system for managing and distributing menus to Holly Lodge residents.

## Core Components

### 1. Menu Processing
- PDF to image conversion
- OCR text extraction
- Template matching
- Header processing
- Date extraction

### 2. Web Dashboard
- Menu template management
- System monitoring
- Configuration interface
- Activity logging
- Backup/restore functionality

### 3. Email System
- Incoming menu processing
- Automated distribution
- Error notifications
- Status updates

## Technical Stack

### Backend
- Python 3.8+
- Flask web framework
- OpenCV for image processing
- Tesseract OCR
- Poppler for PDF handling

### Storage
- Local file system
- Temporary processing folders
- Menu template storage

### Email
- IMAP for receiving menus
- SMTP for sending processed menus
- Gmail compatibility

## Configuration

### Environment Variables
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email
SMTP_PASSWORD=your_app_password
DASHBOARD_PASSWORD=admin_access
SECRET_KEY=flask_secret
```

### File Structure
- /app: Main application code
- /templates: HTML templates
- /menu_templates: Menu template storage
- /temp_images: Temporary processing
- /output_images: Processed outputs

## Development Notes

### Running Locally
1. Start web dashboard: `python run.py`
2. Start menu monitor: `python menu_monitor.py`
3. Access dashboard: http://localhost:5000

### Testing
- Run tests: `pytest`
- Test email processing: Send PDF to configured email
- Monitor logs: Check menu_monitor.log

### Common Issues
- Tesseract OCR path configuration
- Poppler binary location
- SMTP authentication
- Template matching accuracy

## Future Improvements
- Enhanced error handling
- Better logging and monitoring
- Template management improvements
- Email template customization