# Menu System

A robust menu management system for handling menu templates and automated email distribution.

## Features

### Core Functionality
- 📅 Menu template management (upload, preview, delete)
- 📧 Automated email distribution
- 🔄 Season-based menu rotation
- ⚙️ Configurable settings
- 📊 System status monitoring

### Technical Features
- 🔒 Secure file handling with validation
- 🔄 Automatic file backups
- 📝 Comprehensive activity logging
- ⚡ Redis caching
- 🛡️ Error handling and recovery
- 🎨 Responsive UI with animations

## Technology Stack

### Backend
- Python/Flask
- Supabase (Database & Storage)
- Redis (Caching & State)
- SMTP Email Service

### Frontend
- HTML5/CSS3
- JavaScript/jQuery
- Bootstrap 5
- Custom animations

## Security Features
- File validation & sanitization
- Size limits & type restrictions
- Backup system
- Error logging & monitoring
- Rate limiting
- Session management

## System Requirements
- Python 3.8+
- Redis server
- SMTP server access
- Supabase account

## Environment Variables
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
REDIS_URL=your_redis_url
SMTP_SERVER=smtp_server
SMTP_PORT=smtp_port
SMTP_USERNAME=smtp_username
SMTP_PASSWORD=smtp_password
DASHBOARD_PASSWORD=admin_password
SECRET_KEY=flask_secret_key
```

## Database Schema

### menu_settings
- start_date: date
- days_in_advance: integer
- recipient_emails: text[]
- season: text
- created_at: timestamp

### menu_templates
- season: text
- week: integer
- file_path: text
- file_url: text
- file_type: text
- file_size: integer
- updated_at: timestamp

### activity_log
- action: text
- details: text
- status: text
- created_at: timestamp

## File Storage
- Bucket: menu-templates
- Supported types: PDF, JPEG, PNG
- Size limit: 5MB
- Automatic backups

## Maintenance
- Debug mode for troubleshooting
- Activity logging
- System status monitoring
- Connection health checks
- Automatic retry mechanisms

## Future Enhancements
- Email template customization
- Advanced preview features
- Analytics dashboard
- Multi-language support
- API documentation

## Overview
Automated system for managing and sending periodic menus to residents.

## Repository
Public repository: https://github.com/Kramfitt/holly_menus

Note: This is a public repository. All sensitive data (passwords, keys, etc.) 
must be stored in environment variables, never committed to the repository.

## Core Components
1. Web Dashboard (menu_dashboard)
   - Menu preview and management
   - Settings configuration
   - System status monitoring
   - Backup/restore functionality
   - Activity logging

2. Worker Service (menu_worker)
   - Automated menu sending
   - Schedule management
   - Error notifications
   - Activity logging

## Infrastructure
- Hosting: Render.com
- Database: Supabase
- Cache: Redis
- Email: SMTP (Gmail)

## Key Features
- Menu rotation (1&2 vs 3&4)
- Season handling (Summer/Winter)
- Email notifications
- System monitoring
- Backup/restore
- Activity logging

## Deployment
- Auto-deploys from GitHub main branch
- Two Render services:
  1. menu_dashboard (Web)
  2. menu_worker (Worker)

## Deployment Notes

### Render Setup
1. Services Required:
   - Web Service (Python)
   - Background Worker

2. Environment Variables:
   All variables must be set in Render dashboard:
   ```
   SUPABASE_URL=
   SUPABASE_KEY=
   REDIS_URL=
   SMTP_SERVER=
   SMTP_PORT=
   SMTP_USERNAME=
   SMTP_PASSWORD=
   SECRET_KEY=
   DASHBOARD_PASSWORD=
   ```

3. Build Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn wsgi:app`

4. Key Files:
   - wsgi.py (Flask app entry point)
   - Procfile (Render service definitions)
   - requirements.txt (Python dependencies)

### Monitoring
1. Render Dashboard:
   - View logs: Services → holly-menus → Logs
   - Check Events tab for build/deploy status
   - Monitor Resource usage

2. Common Issues:
   - Check gunicorn logs for app startup issues
   - Verify environment variables are set
   - Monitor Redis connection
   - Check Supabase connectivity

3. Health Checks:
   - /health endpoint should return 200
   - Worker service logs should show activity
   - Redis connection status
   - Email service status

## Development History
- Started with basic menu sending system
- Added web interface
- Implemented menu rotation
- Added season handling
- Enhanced with monitoring and backup
- Added professional UI and notifications

## Future Improvements
- Enhanced email templates
- More detailed reporting
- Additional backup options
- Extended monitoring capabilities

## Recent Updates
- Reorganized code using Flask Blueprint and App Factory pattern
- Implemented proper service classes (MenuService, EmailService)
- Added centralized configuration in config module
- Set up basic testing framework with pytest
- Fixed season calculation bug
- Improved error handling and logging

## Project Structure

### Worker Service Structure
1. Files:
   ```
   worker/
   ├── __init__.py        # Package marker
   ├── worker.py          # Main worker process
   ├── scheduler.py       # Menu scheduling logic
   └── main.py           # Entry point (future use)
   ```

2. Key Components:
   - worker.py: Main worker process that runs on Render
   - scheduler.py: Handles menu timing and rotation
   - MenuService: Calculates next menu to send
   - EmailService: Handles email composition and sending

3. Configuration:
   - Procfile points to worker.py
   - Uses same env vars as web service
   - Shares services with web app 

### Deployment Status
1. Web Service (menu_dashboard)
   - URL: https://holly-menus.onrender.com
   - Health Check: /health endpoint
   - Monitor: Render Dashboard → Services → holly-menus → Logs

2. Worker Service (menu_worker)
   - Monitor: Render Dashboard → Services → holly-menus-worker → Logs
   - Status: Check Redis connection and activity logs 