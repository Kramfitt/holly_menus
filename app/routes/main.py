from flask import (
    Flask, render_template, jsonify, request, session, 
    redirect, url_for, Blueprint, current_app
)
from functools import wraps
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
import sys
import time
import redis
import traceback
from supabase import create_client, Client
from worker import calculate_next_menu, send_menu_email
from config import (
    supabase, redis_client, SMTP_SERVER, SMTP_PORT, 
    SMTP_USERNAME, SMTP_PASSWORD, SECRET_KEY,
    DASHBOARD_PASSWORD
)
from app.utils.logger import Logger
from app.services.menu_service import MenuService
from app.services.email_service import EmailService
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import io
import requests
import pytesseract
import subprocess
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import pytz  # Add this import
from dotenv import load_dotenv
import re
from werkzeug.exceptions import HTTPException

# Load environment variables
load_dotenv()

# Keep only the Blueprint
bp = Blueprint('main', __name__)

# Make timedelta available to templates
@bp.context_processor
def utility_processor():
    return {
        'timedelta': timedelta,
        'datetime': datetime
    }

# Near the top with other configs
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url)

# Ensure initial state exists
if redis_client.get('service_state') is None:
    redis_client.set('service_state', 'false')

# Add near top with other Redis initialization
if redis_client.get('debug_mode') is None:
    redis_client.set('debug_mode', 'false')

# Initialize Supabase client
supabase = create_client(
    supabase_url=os.getenv('SUPABASE_URL'),
    supabase_key=os.getenv('SUPABASE_KEY')
)

# Remove any proxy settings if they exist
if hasattr(supabase, '_http_client'):
    if hasattr(supabase._http_client, 'proxies'):
        delattr(supabase._http_client, 'proxies')

logger = Logger()

# Initialize services
menu_service = MenuService(db=supabase, storage=supabase.storage)
email_service = EmailService(config={
    'SMTP_SERVER': SMTP_SERVER,
    'SMTP_PORT': SMTP_PORT,
    'SMTP_USERNAME': SMTP_USERNAME,
    'SMTP_PASSWORD': SMTP_PASSWORD
})

# Update get_service_state to handle missing STATE_FILE
def get_service_state():
    """Get service state from Redis instead of file"""
    try:
        state = redis_client.get('service_state')
        return {
            "active": state == b'true',
            "last_updated": datetime.now()
        }
    except Exception as e:
        logger.log_activity(
            action="Service State Error",
            details=str(e),
            status="error"
        )
        return {"active": False, "last_updated": None}

# Update save_service_state to use Redis
def save_service_state(active):
    """Save service state to Redis"""
    try:
        redis_client.set('service_state', str(active).lower())
        return True
    except Exception as e:
        logger.log_activity(
            action="Service State Save Error",
            details=str(e),
            status="error"
        )
        return False

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

def handle_error(e, action="System Error"):
    """Centralized error handling"""
    error_details = str(e)
    stack_trace = traceback.format_exc()
    
    # Log the error
    logger.log_activity(
        action=action,
        details=f"Error: {error_details}\nStack trace: {stack_trace}",
        status="error"
    )
    
    if current_app.debug:
        return f"Error: {error_details}\n\nStack trace:\n{stack_trace}"
    return "An error occurred. Please try again or contact support."

def rate_limit(key, limit=5, period=60):
    """Basic rate limiting using Redis"""
    try:
        current = int(redis_client.get(f"ratelimit:{key}") or 0)
        if current >= limit:
            return False
            
        pipe = redis_client.pipeline()
        pipe.incr(f"ratelimit:{key}")
        pipe.expire(f"ratelimit:{key}", period)
        pipe.execute()
        return True
        
    except Exception as e:
        logger.log_activity(
            action="Rate Limit Error",
            details=str(e),
            status="error"
        )
        return True  # Allow on error

@bp.route('/login', methods=['GET', 'POST'])
def login():
    try:
        # Add debug logging
        logger.log_activity(
            action="Login Page Access",
            details=f"Method: {request.method}, IP: {request.remote_addr}",
            status="info"
        )

        # Rate limit by IP
        if not rate_limit(f"login:{request.remote_addr}", limit=5, period=300):
            logger.log_activity(
                action="Login Rate Limited",
                details=f"IP: {request.remote_addr}",
                status="warning"
            )
            return render_template('login.html', 
                error="Too many attempts. Please try again later.")

        if request.method == 'POST':
            dashboard_password = current_app.config.get('DASHBOARD_PASSWORD')
            submitted_password = request.form.get('password')
            
            # Check configuration
            if not dashboard_password:
                logger.log_activity(
                    action="Login Error",
                    details="DASHBOARD_PASSWORD not configured",
                    status="error"
                )
                return render_template('login.html', 
                    error="System configuration error. Please contact administrator.")

            # Validate input
            if not submitted_password:
                return render_template('login.html', 
                    error="Password is required")

            # Check password (use constant-time comparison)
            if submitted_password == dashboard_password:
                # Set session variables
                session.clear()  # Clear any existing session
                session['logged_in'] = True
                session['login_time'] = datetime.now().isoformat()
                session.permanent = True  # Make session persistent
                
                logger.log_activity(
                    action="Login Success",
                    details="User logged in successfully",
                    status="success"
                )
                
                return redirect(url_for('main.index'))
            
            # Failed login attempt
            logger.log_activity(
                action="Login Failed",
                details="Invalid password attempt",
                status="warning"
            )
            return render_template('login.html', 
                error="Invalid password")
                
    except Exception as e:
        # Add detailed error logging
        error_details = str(e)
        stack_trace = traceback.format_exc()
        logger.log_activity(
            action="Login System Error",
            details=f"Error: {error_details}\nStack trace: {stack_trace}",
            status="error"
        )
        
        # In debug mode, show full error
        if current_app.debug:
            return render_template('login.html', 
                error=f"Error: {error_details}\n\nStack trace:\n{stack_trace}")
        
        # In production, show generic error
        return render_template('login.html', 
            error="An error occurred. Please try again or contact support.")
            
    # GET request - show login form
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('main.login'))

@bp.route('/')
@login_required
def index():
    try:
        # Get service state safely
        service_active = get_redis_value('service_state', b'false') == b'true'
        
        # Get next menu info
        next_menu = calculate_next_menu()
        if not next_menu:
            logger.log_activity(
                action="Menu Calculation",
                details="Could not calculate next menu",
                status="warning"
            )
        
        # Get recent activity
        try:
            activity_response = supabase.table('activity_log')\
                .select('*')\
                .order('created_at', ascending=False)\
                .limit(10)\
                .execute()
            recent_activity = activity_response.data
        except Exception as e:
            logger.log_activity(
                action="Activity Log Error",
                details=str(e),
                status="error"
            )
            recent_activity = []
        
        return render_template('index.html',
                             service_active=service_active,
                             next_menu=next_menu,
                             recent_activity=recent_activity)
                             
    except Exception as e:
        error_msg = handle_error(e, "Dashboard Error")
        return render_template('error.html', error=error_msg)

@bp.route('/preview')
@login_required
def preview():
    try:
        # Get current settings
        settings = get_menu_settings()
        
        # Get next menu details
        next_menu = menu_service.calculate_next_menu()
        
        return render_template('preview.html', 
                             settings=settings,
                             next_menu=next_menu)
                             
    except Exception as e:
        logger.log_activity(
            action="Preview Page Load Failed",
            details=str(e),
            status="error"
        )
        return render_template('preview.html', error=str(e))

# Add API endpoint for preview rendering
@bp.route('/api/preview', methods=['GET'])
def api_preview_menu():
    try:
        season = request.args.get('season')
        week = request.args.get('week')
        start_date = request.args.get('date')
        
        if not all([season, week, start_date]):
            return "Missing required parameters", 400
            
        # Get menu template
        menu_response = supabase.table('menus')\
            .select('*')\
            .eq('season', season)\
            .eq('week', week)\
            .execute()
            
        if not menu_response.data:
            return f"No template found for {season} week {week}", 404
            
        menu = menu_response.data[0]
        date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        
        # Generate preview
        preview_url = menu_service.generate_preview(menu, date_obj)
        
        return f'<div class="preview-container">' \
               f'<img src="{preview_url}" class="img-fluid" alt="Menu Preview">' \
               f'<div class="mt-2 text-muted">Preview generated for {season.title()} Week {week}</div>' \
               f'</div>'
               
    except Exception as e:
        logger.log_activity(
            action="Preview Generation Failed",
            details=str(e),
            status="error"
        )
        return str(e), 500

def validate_template(file, season, week):
    """Validate template upload"""
    errors = []
    
    # Check file
    if not file:
        errors.append("No file provided")
    elif not file.filename:
        errors.append("Invalid filename")
    else:
        # Check file type
        allowed = {'png', 'jpg', 'jpeg', 'pdf'}
        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext not in allowed:
            errors.append(f"File type not allowed. Must be: {', '.join(allowed)}")
            
        # Check file size (max 5MB)
        if len(file.read()) > 5 * 1024 * 1024:
            errors.append("File too large (max 5MB)")
        file.seek(0)  # Reset file pointer
        
    # Check season
    if not season or season.lower() not in ['summer', 'winter']:
        errors.append("Invalid season (must be summer or winter)")
        
    # Check week
    try:
        week_num = int(week)
        if week_num < 1 or week_num > 4:
            errors.append("Week must be between 1 and 4")
    except (ValueError, TypeError):
        errors.append("Invalid week number")
        
    return errors

@bp.route('/api/template', methods=['POST'])
@login_required
def upload_template():
    try:
        if 'template' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['template']
        season = request.form.get('season')
        week = request.form.get('week')
        
        # Validate template
        errors = validate_template(file, season, week)
        if errors:
            return jsonify({
                'error': 'Validation failed',
                'details': errors
            }), 400
            
        # Secure the filename
        filename = secure_filename(file.filename)
        file_path = f"menus/{season}_{week}_{filename}"
        
        # Upload to Supabase Storage
        supabase.storage.from_('menus').upload(
            file_path,
            file.read(),
            {'content-type': file.content_type}
        )
        
        # Get public URL
        file_url = supabase.storage.from_('menus').get_public_url(file_path)
        
        # Store in database
        response = safe_supabase_query(
            'menu_templates',
            action="insert",
            data={
                'season': season.lower(),
                'week': int(week),
                'file_path': file_path,
                'file_url': file_url,
                'created_at': datetime.now().isoformat()
            }
        )
        
        if response is None:
            raise Exception("Failed to save template")
            
        logger.log_activity(
            action="Template Uploaded",
            details=f"Uploaded template for {season} week {week}",
            status="success"
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        error_msg = handle_error(e, "Template Upload Failed")
        return jsonify({'error': error_msg}), 500

@bp.route('/api/template', methods=['DELETE'])
@login_required
def delete_template():
    try:
        data = request.json
        season = data.get('season')
        week = data.get('week')
        
        if not season or not week:
            return jsonify({'error': 'Missing season or week'}), 400
            
        # Get template
        template = supabase.table('menus')\
            .select('*')\
            .eq('season', season)\
            .eq('week', week)\
            .execute()
            
        if not template.data:
            return jsonify({'error': 'Template not found'}), 404
            
        # Delete from storage
        file_path = template.data[0]['file_path']
        supabase.storage.from_('menus').remove([file_path])
        
        # Delete from database
        supabase.table('menus')\
            .delete()\
            .eq('season', season)\
            .eq('week', week)\
            .execute()
            
        logger.log_activity(
            action="Template Deleted",
            details=f"Deleted {season} week {week} template",
            status="success"
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.log_activity(
            action="Template Delete Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'error': str(e)}), 500

@bp.route('/system-check')
def system_check():
    try:
        # Get current settings
        settings_response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', ascending=False)\
            .limit(1)\
            .execute()
        
        # Calculate next menu details using worker logic
        next_menu = None
        if settings_response.data:
            current_settings = settings_response.data[0]
            start_date = datetime.strptime(current_settings['start_date'], '%Y-%m-%d').date()
            today = datetime.now().date()
            
            # Use worker's calculate_next_menu logic
            weeks_since_start = (today - start_date).days // 7
            periods_elapsed = weeks_since_start // 2
            next_period_start = start_date + timedelta(days=periods_elapsed * 14)
            send_date = next_period_start - timedelta(days=current_settings['days_in_advance'])
            
            if today > send_date:
                next_period_start += timedelta(days=14)
                send_date += timedelta(days=14)
            
            is_odd_period = (periods_elapsed % 2) == 0
            menu_pair = "1 & 2" if is_odd_period else "3 & 4"
            
            next_menu = {
                'send_date': send_date,
                'period_start': next_period_start,
                'menu_pair': menu_pair,
                'season': current_settings['season']
            }
        
        return render_template(
            'system-check.html',
            settings=settings_response.data[0] if settings_response.data else None,
            next_menu=next_menu
        )
        
    except Exception as e:
        print(f"❌ System check error: {str(e)}")
        return f"Error loading system status: {str(e)}", 500

def send_menu_email(start_date, recipient_list, season):
    try:
        # Get menu data
        response = supabase.table('menus')\
            .select('*')\
            .eq('season', season)\
            .execute()
            
        if not response.data:
            return "Menu not found", 404
            
        menu = response.data[0]
        
        # Generate preview image
        preview_date = start_date.strftime('%Y-%m-%d')
        preview_path = f"previews/preview_{menu['id']}_{preview_date}.{menu['file_type']}"
        
        # Get the preview URL
        preview_url = supabase.storage.from_('menus').get_public_url(preview_path)
        
        # Download the preview image
        img_response = requests.get(preview_url)
        
        # Email setup
        sender_email = os.getenv('SMTP_USERNAME')
        sender_password = os.getenv('SMTP_PASSWORD')
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Holly Lea Menu - Week Starting {start_date.strftime('%d %B %Y')}"
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipient_list)
        
        # HTML Email content
        html_content = f"""
        <html>
            <body>
                <h2>Holly Lea Menu</h2>
                <p>Please find attached the menu for the week starting {start_date.strftime('%d %B %Y')}.</p>
                <p>Kind regards,<br>Holly Lea</p>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html_content, 'html'))
        
        # Attach the preview image
        attachment = MIMEImage(img_response.content)
        attachment.add_header('Content-Disposition', 'attachment', 
                            filename=f"menu_{start_date.strftime('%Y%m%d')}.{menu['file_type']}")
        msg.attach(attachment)
        
        # Send email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
            
        return "Email sent successfully"
        
    except Exception as e:
        print(f"❌ Email error: {str(e)}")
        return f"Failed to send email: {str(e)}", 500

@bp.route('/api/send-menu', methods=['POST'])
def api_send_menu():
    try:
        data = request.json
        menu_id = data.get('menu_id')
        date = datetime.strptime(data.get('date'), '%Y-%m-%d')
        recipients = data.get('recipients', [])
        
        if not menu_id or not date or not recipients:
            return "Missing required data", 400
            
        result = send_menu_email(date, recipients, date.strftime('%Y-%m-%d'))
        return result
        
    except Exception as e:
        print(f"❌ Send menu error: {str(e)}")
        return f"Failed to send menu: {str(e)}", 500

def validate_email(email):
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_emails(emails):
    """Validate a list of email addresses"""
    errors = []
    valid_emails = []
    
    for email in emails:
        email = email.strip()
        if not email:
            continue
            
        if validate_email(email):
            valid_emails.append(email)
        else:
            errors.append(f"Invalid email address: {email}")
            
    if not valid_emails:
        errors.append("At least one valid email address is required")
        
    return errors, valid_emails

def validate_settings(data):
    """Validate settings data"""
    errors = []
    
    # Required fields
    if not data.get('start_date'):
        errors.append("Start date is required")
    else:
        try:
            datetime.strptime(data['start_date'], '%Y-%m-%d')
        except ValueError:
            errors.append("Invalid start date format")
            
    # Days in advance
    try:
        days = int(data.get('days_in_advance', 0))
        if days < 1 or days > 14:
            errors.append("Days in advance must be between 1 and 14")
    except ValueError:
        errors.append("Invalid days in advance value")
        
    # Email validation
    email_errors, valid_emails = validate_emails(data.get('recipient_emails', []))
    errors.extend(email_errors)
    if valid_emails:
        data['recipient_emails'] = valid_emails  # Update with validated emails
        
    return errors

@bp.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Validate settings
        errors = validate_settings(data)
        if errors:
            return jsonify({
                'error': 'Validation failed',
                'details': errors
            }), 400
            
        # Create settings object
        settings = {
            'start_date': data['start_date'],
            'days_in_advance': int(data['days_in_advance']),
            'recipient_emails': data['recipient_emails'],
            'season': data.get('season', 'summer'),
            'season_change_date': data.get('season_change_date'),
            'created_at': datetime.now().isoformat()
        }
        
        # Insert new settings
        response = safe_supabase_query(
            'menu_settings',
            action="insert",
            data=settings
        )
        
        if response is None:
            raise Exception("Failed to save settings")
            
        logger.log_activity(
            action="Settings Updated",
            details="Menu settings updated successfully",
            status="success"
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        error_msg = handle_error(e, "Settings API Error")
        return jsonify({'error': error_msg}), 500

@bp.route('/api/email-status', methods=['GET'])
def get_email_status():
    try:
        state = redis_client.get('service_state')
        return jsonify({'active': state == b'true'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/toggle-email', methods=['POST'])
def toggle_email():
    try:
        # Get current state from Redis
        current_state = redis_client.get('service_state')
        if current_state is None:
            # Initialize if not set
            current_state = b'false'
            redis_client.set('service_state', 'false')
        
        # Toggle state
        new_state = 'false' if current_state == b'true' else 'true'
        
        # Set new state
        redis_client.set('service_state', new_state)
        
        # Log the change
        logger.log_activity(
            action="Email Service Toggled",
            details=f"Email service {'activated' if new_state == 'true' else 'deactivated'}",
            status="success"
        )
        
        print(f"Service state toggled to: {new_state}")  # Debug log
        
        return jsonify({'active': new_state == 'true'})
    except Exception as e:
        print(f"Toggle error: {str(e)}")  # Debug log
        logger.log_activity(
            action="Email Service Toggle Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'error': str(e)}), 500

def send_email_safely(to_email, subject, body, timeout=30):
    """Send email with timeout and error handling"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Holly Lea Menus <{SMTP_USERNAME}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Set timeout for SMTP operations
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=timeout) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            
        return True
        
    except smtplib.SMTPException as e:
        logger.log_activity(
            action="SMTP Error",
            details=f"Failed to send email to {to_email}: {str(e)}",
            status="error"
        )
        return False
    except Exception as e:
        logger.log_activity(
            action="Email Error",
            details=f"Failed to send email to {to_email}: {str(e)}",
            status="error"
        )
        return False

@bp.route('/api/test-email', methods=['POST'])
@login_required
def send_test_email():
    try:
        email = request.json.get('email')
        if not email:
            return jsonify({'error': 'Email address required'}), 400
            
        # Validate email format
        if not validate_email(email):
            return jsonify({'error': 'Invalid email address format'}), 400
            
        # Check SMTP settings
        if not all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD]):
            return jsonify({'error': 'SMTP settings not configured'}), 500
            
        # Send test email with timeout
        success = send_email_safely(
            email,
            "Test Email from Holly Lea Menu System",
            "This is a test email from the Holly Lea Menu System.",
            timeout=10
        )
        
        if not success:
            return jsonify({'error': 'Failed to send email'}), 500
            
        logger.log_activity(
            action="Test Email Sent",
            details=f"Test email sent to {email}",
            status="success"
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        error_msg = handle_error(e, "Test Email Failed")
        return jsonify({'error': error_msg}), 500

@bp.route('/api/debug-mode', methods=['GET', 'POST'])
@login_required
def debug_mode():
    try:
        if request.method == 'POST':
            data = request.get_json()
            if data is None or 'active' not in data:
                return jsonify({'error': 'Missing active state'}), 400
                
            redis_client.set('debug_mode', str(data['active']).lower())
            
            logger.log_activity(
                action="Debug Mode",
                details=f"Debug mode {'enabled' if data['active'] else 'disabled'}",
                status="info"
            )
            
            return jsonify({'success': True, 'active': data['active']})
        else:
            is_active = redis_client.get('debug_mode') == b'true'
            return jsonify({'active': is_active})
            
    except Exception as e:
        logger.log_activity(
            action="Debug Mode Error",
            details=str(e),
            status="error"
        )
        return jsonify({'error': str(e)}), 500

def validate_force_send():
    """Validate force send requirements"""
    errors = []
    
    # Check debug mode
    if redis_client.get('debug_mode') != b'true':
        errors.append("Debug mode must be enabled")
        
    # Check settings exist
    settings = get_menu_settings()
    if not settings:
        errors.append("No menu settings configured")
    elif not settings.get('recipient_emails'):
        errors.append("No recipient emails configured")
        
    # Check next menu can be calculated
    next_menu = calculate_next_menu()
    if not next_menu:
        errors.append("Could not calculate next menu")
        
    return errors, settings, next_menu

@bp.route('/api/force-send', methods=['POST'])
@login_required
def force_send():
    try:
        # Validate requirements
        errors, settings, next_menu = validate_force_send()
        if errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': errors
            }), 400
            
        # Send menu
        success = send_menu_email(
            start_date=next_menu['period_start'],
            recipient_list=settings['recipient_emails'],
            season=next_menu['season'],
            week_number=next_menu['week']
        )
        
        message = "Test menu sent successfully!" if success else "Failed to send test menu"
        logger.log_activity(
            action="Force Send Menu",
            details=message,
            status="debug" if success else "error"
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        error_msg = handle_error(e, "Force Send Failed")
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

def get_menu_settings():
    """Get current menu settings"""
    try:
        settings_response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', ascending=False)\
            .limit(1)\
            .execute()
            
        if not settings_response.data:
            return None
            
        settings = settings_response.data[0]
        
        # Convert date strings to dates
        if settings.get('start_date'):
            settings['start_date'] = datetime.strptime(
                settings['start_date'], 
                '%Y-%m-%d'
            ).date()
            
        if settings.get('season_change_date'):
            settings['season_change_date'] = datetime.strptime(
                settings['season_change_date'], 
                '%Y-%m-%d'
            ).date()
            
        return settings
        
    except Exception as e:
        logger.log_activity(
            action="Settings Fetch Failed",
            details=str(e),
            status="error"
        )
        return None

@bp.route('/api/email-health', methods=['GET'])
def check_email_health():
    try:
        state = redis_client.get('service_state')
        return jsonify({'active': state == b'true'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/clear-activity-log', methods=['POST'])
@login_required
def clear_activity_log():
    try:
        # Delete all records using a filter that's always true
        response = safe_supabase_query(
            'activity_log',
            action="delete",
            filter_column='id',
            filter_value=0,
            filter_operator='gte'  # Greater than or equal to 0 (all records)
        )
        
        if response is None:
            raise Exception("Failed to clear activity log")
            
        logger.log_activity(
            action="Activity Log Cleared",
            details="Activity log cleared",
            status="success"
        )
        
        return jsonify({
            'success': True,
            'message': "Activity log cleared successfully"
        })
            
    except Exception as e:
        error_msg = handle_error(e, "Clear Log Failed")
        return jsonify({
            'error': error_msg,
            'message': "Failed to clear activity log"
        }), 500

def log_activity(action, details, status):
    """Log an activity with validated status"""
    # Define valid status values that match Supabase constraint
    VALID_STATUSES = {
        'success': 'success',
        'warning': 'warning',
        'error': 'error',
        'info': 'info',
        'debug': 'debug'
    }
    
    try:
        # Normalize and validate status
        normalized_status = status.lower() if status else 'info'
        final_status = VALID_STATUSES.get(normalized_status, 'info')
        
        # Insert log entry
        supabase.table('activity_log').insert({
            'action': action,
            'details': details,
            'status': final_status,
            'created_at': datetime.now().isoformat()
        }).execute()
        
    except Exception as e:
        print(f"❌ Logging error: {str(e)}")  # Debug print

@bp.route('/settings')
@login_required
def settings():
    try:
        # Get current settings safely
        settings_response = safe_supabase_query(
            'menu_settings',
            action="select",
            order_by='created_at',
            ascending=False,
            limit=1
        )
        
        if settings_response is None:
            raise Exception("Failed to fetch settings")
            
        current_settings = settings_response.data[0] if settings_response.data else {}
        
        # Get menu templates
        templates_response = supabase.table('menu_templates')\
            .select('*')\
            .execute()
            
        # Initialize template structure
        templates = {
            'summer': {},
            'winter': {}
        }
        
        # Organize templates
        if templates_response.data:
            for template in templates_response.data:
                season = template.get('season', '').lower()
                week = template.get('week')
                if season in templates:
                    templates[season][str(week)] = template
        
        logger.log_activity(
            action="Settings Page Load",
            details="Settings page accessed",
            status="info"
        )
        
        return render_template('settings.html',
                             settings=current_settings,
                             templates=templates,
                             error=None)
                             
    except Exception as e:
        error_msg = handle_error(e, "Settings Page Error")
        # Return the error template with empty data
        return render_template('settings.html', 
                             settings={},
                             templates={'summer': {}, 'winter': {}},
                             error=error_msg)

@bp.route('/status')
@login_required
def system_status():
    try:
        # Log system metrics
        log_system_metrics()
        
        # Get service states
        email_active = redis_client.get('service_state') == b'true'
        debug_mode = redis_client.get('debug_mode') == b'true'
        maintenance_mode = check_maintenance_mode()
        
        # Get connection status
        db_status = check_database()
        redis_status = check_redis()
        smtp_status = all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD])
        
        return render_template('status.html',
                             email_active=email_active,
                             debug_mode=debug_mode,
                             maintenance_mode=maintenance_mode,
                             db_status=db_status,
                             redis_status=redis_status,
                             smtp_status=smtp_status)
                             
    except Exception as e:
        error_msg = handle_error(e, "Status Page Error")
        return render_template('status.html', error=error_msg)

@bp.before_request
def check_session():
    """Protect against session hijacking and timeout"""
    try:
        if request.endpoint and 'static' not in request.endpoint:
            if request.endpoint not in ['main.login', 'main.logout', 'main.health_check']:
                if not session.get('logged_in'):
                    return redirect(url_for('main.login'))
                
                # Check session age
                login_time = session.get('login_time')
                if login_time:
                    login_datetime = datetime.fromisoformat(login_time)
                    if datetime.now() - login_datetime > timedelta(hours=8):
                        session.clear()
                        return redirect(url_for('main.login', 
                            error="Session expired. Please login again."))
                        
    except Exception as e:
        handle_error(e, "Session Check Error")
        session.clear()
        return redirect(url_for('main.login', 
            error="Session error. Please login again."))

@bp.route('/api/config-check')
def config_check():
    """Check configuration status"""
    try:
        return jsonify({
            'dashboard_password_set': bool(current_app.config.get('DASHBOARD_PASSWORD')),
            'secret_key_set': bool(current_app.config.get('SECRET_KEY')),
            'session_config': {
                'permanent_lifetime': str(current_app.config.get('PERMANENT_SESSION_LIFETIME')),
                'cookie_secure': current_app.config.get('SESSION_COOKIE_SECURE'),
                'cookie_httponly': current_app.config.get('SESSION_COOKIE_HTTPONLY')
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_redis_value(key, default=None, max_retries=3):
    """Safely get Redis value with retries"""
    for attempt in range(max_retries):
        try:
            value = redis_client.get(key)
            return value if value is not None else default
        except Exception as e:
            if attempt == max_retries - 1:
                logger.log_activity(
                    action="Redis Error",
                    details=f"Error getting {key} after {max_retries} attempts: {str(e)}",
                    status="error"
                )
                return default
            time.sleep(0.1 * (attempt + 1))  # Exponential backoff

def set_redis_value(key, value, max_retries=3):
    """Safely set Redis value with retries"""
    for attempt in range(max_retries):
        try:
            redis_client.set(key, value)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                logger.log_activity(
                    action="Redis Error",
                    details=f"Error setting {key} after {max_retries} attempts: {str(e)}",
                    status="error"
                )
                return False
            time.sleep(0.1 * (attempt + 1))

def safe_supabase_query(table, action="query", timeout=10, **kwargs):
    """Execute Supabase queries with timeout"""
    try:
        start_time = time.time()
        query = supabase.table(table)
        
        if action == "select":
            query = query.select(kwargs.get('columns', '*'))
        elif action == "insert":
            return query.insert(kwargs.get('data')).execute()
        elif action == "delete":
            query = query.delete()
            # Add filter for delete
            if kwargs.get('filter_column'):
                query = query.filter(
                    kwargs['filter_column'],
                    kwargs.get('filter_operator', 'eq'),
                    kwargs['filter_value']
                )
            
        if kwargs.get('order_by'):
            query = query.order(kwargs['order_by'], ascending=kwargs.get('ascending', True))
            
        if kwargs.get('limit'):
            query = query.limit(kwargs['limit'])
            
        result = query.execute()
        
        # Check if query took too long
        if time.time() - start_time > timeout:
            logger.log_activity(
                action="Slow Query Warning",
                details=f"Query to {table} took more than {timeout} seconds",
                status="warning"
            )
            
        return result
        
    except Exception as e:
        logger.log_activity(
            action=f"Database Error ({action})",
            details=f"Error in {table}: {str(e)}",
            status="error"
        )
        return None

def register_filters(app):
    """Register custom template filters"""
    
    @app.template_filter('datetime')
    def format_datetime(value):
        """Format datetime to readable string"""
        if not value:
            return ''
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                dt = value
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(value)

    @app.template_filter('status_color')
    def status_color(status):
        """Convert status to Bootstrap color class"""
        colors = {
            'success': 'success',
            'warning': 'warning',
            'error': 'danger',
            'info': 'info',
            'debug': 'secondary'
        }
        return colors.get(status.lower() if status else '', 'secondary')

    # Don't return app, just register the filters
    return None

# Export both bp and register_filters at the top
__all__ = ['bp', 'register_filters']

@bp.route('/health')
def health_check():
    """Basic health check endpoint"""
    try:
        # Check all services
        redis_ok = check_redis()
        db_ok = check_database()
        smtp_ok = all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD])
        
        status = "healthy" if all([redis_ok, db_ok, smtp_ok]) else "unhealthy"
        
        # Get more detailed status
        details = {
            'redis': {
                'status': 'connected' if redis_ok else 'disconnected',
                'last_check': datetime.now().isoformat()
            },
            'database': {
                'status': 'connected' if db_ok else 'disconnected',
                'last_check': datetime.now().isoformat()
            },
            'smtp': {
                'status': 'configured' if smtp_ok else 'not_configured',
                'server': SMTP_SERVER,
                'port': SMTP_PORT
            }
        }
        
        return jsonify({
            'status': status,
            'services': details,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        error_msg = handle_error(e, "Health Check Failed")
        return jsonify({
            'status': 'error',
            'error': error_msg,
            'timestamp': datetime.now().isoformat()
        }), 500

@bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('error.html', 
        error="The requested page was not found."), 404

@bp.app_errorhandler(500)
def internal_error(e):
    return render_template('error.html',
        error="An internal server error occurred."), 500

@bp.app_errorhandler(403)
def forbidden_error(e):
    return render_template('error.html',
        error="You don't have permission to access this page."), 403

@bp.app_errorhandler(405)
def method_not_allowed(e):
    return render_template('error.html',
        error="This method is not allowed for this endpoint."), 405

@bp.app_errorhandler(429)
def too_many_requests(e):
    return render_template('error.html',
        error="Too many requests. Please try again later."), 429

def check_maintenance_mode():
    """Check if system is in maintenance mode"""
    try:
        return redis_client.get('maintenance_mode') == b'true'
    except:
        return False

@bp.before_request
def handle_maintenance():
    """Handle maintenance mode"""
    if check_maintenance_mode():
        # Allow health check endpoint
        if request.endpoint != 'main.health_check':
            return render_template('maintenance.html'), 503

@bp.route('/api/maintenance', methods=['POST'])
@login_required
def toggle_maintenance():
    """Toggle maintenance mode"""
    try:
        current = check_maintenance_mode()
        redis_client.set('maintenance_mode', str(not current).lower())
        
        logger.log_activity(
            action="Maintenance Mode",
            details=f"Maintenance mode {'disabled' if current else 'enabled'}",
            status="info"
        )
        
        return jsonify({'active': not current})
    except Exception as e:
        error_msg = handle_error(e, "Maintenance Toggle Failed")
        return jsonify({'error': error_msg}), 500

# Add database connection check
def check_database():
    """Check database connection"""
    try:
        safe_supabase_query(
            'menu_settings',
            action="select",
            limit=1,
            timeout=5  # Short timeout for health check
        )
        return True
    except Exception as e:
        logger.log_activity(
            action="Database Check Failed",
            details=str(e),
            status="error"
        )
        return False

# Add Redis connection check
def check_redis():
    """Check Redis connection"""
    try:
        return redis_client.ping()
    except Exception as e:
        logger.log_activity(
            action="Redis Check Failed",
            details=str(e),
            status="error"
        )
        return False

# Add system monitoring
def log_system_metrics():
    """Log system metrics"""
    try:
        # Check service states
        email_active = redis_client.get('service_state') == b'true'
        debug_mode = redis_client.get('debug_mode') == b'true'
        maintenance_mode = check_maintenance_mode()
        
        # Check connections
        redis_ok = check_redis()
        db_ok = check_database()
        smtp_ok = all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD])
        
        # Log metrics
        logger.log_activity(
            action="System Metrics",
            details={
                'services': {
                    'email': email_active,
                    'debug': debug_mode,
                    'maintenance': maintenance_mode
                },
                'connections': {
                    'redis': redis_ok,
                    'database': db_ok,
                    'smtp': smtp_ok
                }
            },
            status="info"
        )
        
    except Exception as e:
        logger.log_activity(
            action="Metrics Logging Failed",
            details=str(e),
            status="error"
        ) 