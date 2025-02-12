# Holly Lea Menu System

## Overview
Automated system for managing and sending periodic menus to residents.

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

## Environment Variables
Required in Render "Menu Scheduler" Environment Group:
- SUPABASE_URL
- SUPABASE_KEY
- SMTP_SERVER
- SMTP_PORT
- SMTP_USERNAME
- SMTP_PASSWORD
- ADMIN_EMAIL
- REDIS_URL

## Database Tables (Supabase)
1. menu_settings
   - System configuration
   - Schedule settings
   - Email recipients

2. menus
   - Menu templates
   - File storage

3. activity_log
   - System events
   - Error tracking

4. notifications
   - System alerts
   - Error notifications

5. backups
   - System backups
   - Restore points

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