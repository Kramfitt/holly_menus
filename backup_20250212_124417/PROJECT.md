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