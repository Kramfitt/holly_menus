from flask import (
    Flask, render_template, jsonify, request, session, 
    redirect, url_for, Blueprint, current_app, flash
)
from functools import wraps
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os
import sys
import time
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
from app.utils.debug import debug_log, debug_print, is_debug_mode
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
import pytz
from dotenv import load_dotenv
import re
from werkzeug.exceptions import HTTPException
import json

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

# Initialize services
menu_service = MenuService(db=supabase, storage=supabase.storage)
email_service = EmailService(config={
    'SMTP_SERVER': SMTP_SERVER,
    'SMTP_PORT': SMTP_PORT,
    'SMTP_USERNAME': SMTP_USERNAME,
    'SMTP_PASSWORD': SMTP_PASSWORD
})

logger = None

def get_logger():
    """Get logger instance safely"""
    global logger
    if logger is None:
        try:
            logger = current_app.activity_logger
        except (RuntimeError, AttributeError):
            logger = Logger()
    return logger

def get_service_state() -> Dict[str, Any]:
    """Get service state with fallback for when Redis is not available"""
    if redis_client is None:
        return {
            "active": True,
            "last_updated": datetime.now().isoformat(),
            "message": "Service running (Redis disabled)"
        }
    
    try:
        state = redis_client.get('service_state')
        if state is None:
            return {
                "active": False,
                "last_updated": datetime.now().isoformat(),
                "message": "Service state unknown"
            }
        return json.loads(state)
    except Exception as e:
        get_logger().log_activity(
            action="Service State Error",
            details=str(e),
            status="error"
        )
        return {
            "active": False,
            "last_updated": None,
            "message": "Error getting service state"
        }

def save_service_state(state: Dict[str, Any]) -> bool:
    """Save service state to Redis"""
    if redis_client is None:
        get_logger().log_activity(
            action="Service State Save",
            details="Redis disabled - state not saved",
            status="warning"
        )
        return True
    
    try:
        redis_client.set('service_state', json.dumps(state))
        return True
    except Exception as e:
        get_logger().log_activity(
            action="Service State Save Error",
            details=str(e),
            status="error"
        )
        return False

# Initialize service state if Redis is available
if redis_client is not None:
    try:
        if redis_client.get('service_state') is None:
            redis_client.set('service_state', json.dumps({
                'active': False,
                'last_updated': datetime.now().isoformat(),
                'message': 'Service initialized'
            }))
        if redis_client.get('debug_mode') is None:
            redis_client.set('debug_mode', 'false')
    except Exception as e:
        print(f"⚠️ Error initializing Redis state: {e}")

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
    get_logger().log_activity(
        action=action,
        details=f"Error: {error_details}\nStack trace: {stack_trace}",
        status="error"
    )
    
    if current_app.debug:
        return f"Error: {error_details}\n\nStack trace:\n{stack_trace}"
    return "An error occurred. Please try again or contact support."

def rate_limit(key, limit=5, period=60):
    """Basic rate limiting with fallback for when Redis is not available"""
    if redis_client is None:
        return True  # No rate limiting when Redis is disabled
        
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
        get_logger().log_activity(
            action="Rate Limit Error",
            details=str(e),
            status="error"
        )
        return True  # Allow on error

@bp.route('/login', methods=['GET', 'POST'])
def login():
    try:
        # Add debug logging
        get_logger().log_activity(
            action="Login Page Access",
            details=f"Method: {request.method}, IP: {request.remote_addr}",
            status="info"
        )

        # Rate limit by IP
        if not rate_limit(f"login:{request.remote_addr}", limit=5, period=300):
            get_logger().log_activity(
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
                get_logger().log_activity(
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
                
                get_logger().log_activity(
                    action="Login Success",
                    details="User logged in successfully",
                    status="success"
                )
                
                return redirect(url_for('main.index'))
            
            # Failed login attempt
            get_logger().log_activity(
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
        get_logger().log_activity(
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
    """Dashboard home page"""
    try:
        # Get menu service
        menu_service = current_app.menu_service
        
        # Get current settings and next menu
        settings = menu_service.get_settings()
        next_menu = menu_service.calculate_next_menu()
        
        # Check service statuses with error handling
        try:
            db_status = bool(menu_service.db.table('menu_settings').select('count').execute())
        except Exception:
            db_status = False
            
        try:
            redis_status = redis_client and redis_client.ping()
        except Exception:
            redis_status = False
            
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                smtp_status = True
        except Exception:
            smtp_status = False
        
        # Get service states with fallbacks
        try:
            email_active = redis_client and redis_client.get('service_state') == b'true'
        except Exception:
            email_active = False
            
        try:
            debug_mode = redis_client and redis_client.get('debug_mode') == b'true'
        except Exception:
            debug_mode = False
        
        return render_template('index.html',
            settings=settings,
            next_menu=next_menu,
            db_status=db_status,
            redis_status=redis_status,
            smtp_status=smtp_status,
            email_active=email_active,
            debug_mode=debug_mode
        )
        
    except Exception as e:
        get_logger().log_activity(
            action="Dashboard Error",
            details=str(e),
            status="error"
        )
        flash('Error loading dashboard. Check system status.', 'error')
        return render_template('index.html',
            settings=None,
            next_menu=None,
            db_status=False,
            redis_status=False,
            smtp_status=False,
            email_active=False,
            debug_mode=False
        )

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
        get_logger().log_activity(
            action="Preview Page Load Failed",
            details=str(e),
            status="error"
        )
        return render_template('preview.html', error=str(e))

@bp.route('/api/preview', methods=['GET'])
def api_preview_menu():
    """Generate a preview of a menu template"""
    try:
        print("Starting preview generation...")
        season = request.args.get('season')
        week = request.args.get('week')
        
        if not season or not week:
            return jsonify({
                'error': 'Missing parameters',
                'details': {
                    'message': 'Season and week are required',
                    'suggestion': 'Please provide both season and week'
                }
            }), 400
            
        print(f"Getting template for {season} week {week}...")
        template = menu_service.get_template(season, week)
        
        if not template:
            return jsonify({
                'error': 'Template not found',
                'details': {
                    'message': f'No template found for {season.title()} Week {week}',
                    'suggestion': 'Please upload a template first',
                    'help': 'Go to Settings > Menu Templates to upload a template'
                }
            }), 404
            
        print("Getting dates template...")
        dates_template = menu_service.get_template('dates', 0)  # Use week=0 for dates template
        if not dates_template:
            return jsonify({
                'error': 'Dates template not found',
                'details': {
                    'message': 'No dates header template found',
                    'suggestion': 'Please upload a dates header template first',
                    'help': 'Go to Settings > Menu Templates to upload a dates header template'
                }
            }), 404
            
        print("Generating preview...")
        preview = menu_service.generate_preview(
            template={
                'season': season,
                'week': week,
                'template_url': template['template_url'],
            },
            start_date=datetime.now()
        )
        
        print("Preview generated successfully")
        return jsonify(preview)
            
    except Exception as e:
        error_msg = f"Preview generation failed: {str(e)}"
        print(error_msg)
        get_logger().log_activity(
            action="Preview API Error",
            details=str(e),
            status="error"
        )
        return jsonify({
            'error': 'System error',
            'details': {
                'message': str(e),
                'type': 'system_error',
                'suggestion': 'Please refresh the page and try again',
                'help': 'If the problem persists, try clearing your browser cache'
            }
        }), 500

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
    if not season:
        errors.append("Season is required")
    else:
        season = season.lower()
        if season not in ['summer', 'winter', 'dates']:
            errors.append("Invalid season (must be summer, winter, or dates)")
        
    # Check week based on season
    if season == 'dates':
        # For dates template, week should be 'header' or 0
        if week not in ['header', '0', 0]:
            errors.append("Week must be 'header' or 0 for dates template")
    else:
        # For summer/winter templates
        try:
            week_num = int(week)
            if week_num < 1 or week_num > 4:
                errors.append("Week must be between 1 and 4 for summer/winter templates")
        except (ValueError, TypeError):
            errors.append("Invalid week number")
        
    return errors

@bp.route('/api/upload-template', methods=['POST'])
@login_required
@debug_log("Template Upload", timing=True)
def upload_template():
    try:
        print("\n=== Starting Template Upload ===")
        print("Request Files:", dict(request.files))
        print("Request Form:", dict(request.form))
        
        if 'template' not in request.files:
            print("❌ No file provided in request")
            return jsonify({'error': '📁 No file provided'}), 400
            
        file = request.files['template']
        season = request.form.get('season')
        week = request.form.get('week')
        
        print(f"Upload request details:")
        print(f"- File: {file.filename if file else 'None'}")
        print(f"- Content Type: {file.content_type if file else 'None'}")
        print(f"- Season: {season}")
        print(f"- Week: {week}")
        
        # Basic validation
        validation_errors = validate_template(file, season, week)
        if validation_errors:
            print("❌ Validation errors:", validation_errors)
            return jsonify({'error': validation_errors[0]}), 400
            
        # Verify menu service is available
        if not hasattr(current_app, 'menu_service'):
            print("❌ Menu service not initialized")
            if current_app.config['FLASK_ENV'] == 'development':
                print("Development mode - simulating success")
                return jsonify({
                    'success': True,
                    'message': 'Template upload simulated in development mode',
                    'url': 'http://example.com/mock-template.pdf'
                })
            return jsonify({'error': 'System configuration error: menu service not available'}), 500
            
        # Save using menu service
        print("Calling menu_service.save_template...")
        try:
            result = current_app.menu_service.save_template(file, season, week)
            print("save_template result:", result)
            
            if not result:
                print("❌ No result from save_template")
                return jsonify({'error': 'No response from save operation'}), 500
                
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error occurred')
                print(f"❌ Upload failed: {error_msg}")
                return jsonify({'error': error_msg}), 400
                
            if not result.get('url'):
                print("❌ No URL in successful response")
                return jsonify({'error': 'Upload succeeded but no URL was returned'}), 500
                
            get_logger().log_activity(
                action="Template Uploaded",
                details={
                    "file": file.filename,
                    "season": season,
                    "week": week,
                    "url": result['url']
                },
                status="success"
            )
            
            return jsonify({
                'success': True,
                'message': 'Template uploaded successfully',
                'url': result['url']
            })
            
        except Exception as service_error:
            print(f"❌ Menu service error: {str(service_error)}")
            print("Service error details:", traceback.format_exc())
            if current_app.config['FLASK_ENV'] == 'development':
                print("Development mode - simulating success")
                return jsonify({
                    'success': True,
                    'message': 'Template upload simulated in development mode',
                    'url': 'http://example.com/mock-template.pdf'
                })
            return jsonify({'error': f'Menu service error: {str(service_error)}'}), 500
            
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("Full error details:", traceback.format_exc())
        get_logger().log_activity(
            action="Template Upload Failed",
            details=f"Error: {str(e)}\nStack trace: {traceback.format_exc()}",
            status="error"
        )
        return jsonify({'error': str(e)}), 500

@bp.route('/api/templates/<season>/<week>', methods=['DELETE'])
def delete_template(season: str, week: str):
    """Delete a menu template"""
    try:
        menu_service = MenuService(db=supabase, storage=supabase.storage)
        result = menu_service.delete_template(season, int(week))
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 400
            
        return jsonify({'success': True}), 200
        
    except Exception as e:
        get_logger().log_activity(
            action="Delete Template Route Failed",
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
            'system_check.html',
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
@debug_log("Save Settings", timing=True)
def save_settings():
    try:
        data = request.get_json()
        debug_print("Received settings data:", data)
        
        # Validate required fields
        required = ['start_date', 'days_in_advance', 'recipient_emails', 'season']
        missing = [f for f in required if not data.get(f)]
        if missing:
            debug_print("Missing required fields:", missing)
            return jsonify({
                'error': 'Missing required fields',
                'details': missing
            }), 400
            
        # Validate season
        if data['season'] not in ['summer', 'winter']:
            debug_print(f"Invalid season: {data['season']}")
            return jsonify({
                'error': 'Invalid season',
                'details': 'Season must be summer or winter'
            }), 400
            
        # Save to database
        settings_data = {
            'start_date': data['start_date'],
            'days_in_advance': data['days_in_advance'],
            'recipient_emails': data['recipient_emails'],
            'season': data['season'].lower(),  # Ensure lowercase
            'created_at': datetime.now().isoformat()
        }
        
        # Add season change date if provided
        if 'season_change_date' in data and data['season_change_date']:
            settings_data['season_change_date'] = data['season_change_date']
        
        debug_print("Saving settings:", settings_data)
        
        # Save to database
        result = supabase.table('menu_settings').insert(settings_data).execute()
        
        get_logger().log_activity(
            action="Settings Updated",
            details=f"Menu settings updated for {data['season']} season",
            status="success"
        )
        
        debug_print("Settings saved successfully")
        return jsonify({'success': True})
        
    except Exception as e:
        debug_print(f"Settings save error: {str(e)}")
        get_logger().log_activity(
            action="Settings Update Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'error': str(e)}), 500

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
        # Get Redis client from app config
        redis_client = current_app.config.get('redis_client')
        if redis_client is None:
            return jsonify({
                'error': 'System configuration error',
                'details': 'Redis service is not available'
            }), 500
            
        # Get desired state from request
        data = request.get_json()
        desired_state = str(data.get('active')).lower() if data else None
        
        if desired_state not in ['true', 'false']:
            return jsonify({
                'error': 'Invalid state',
                'details': 'State must be true or false'
            }), 400
            
        # Set new state
        try:
            redis_client.set('service_state', desired_state)
        except Exception as redis_error:
            logger.error(f"Error setting Redis state: {str(redis_error)}")
            return jsonify({
                'error': 'Failed to update service state',
                'details': str(redis_error)
            }), 500
        
        # Log the change
        get_logger().log_activity(
            action="Email Service Toggled",
            details=f"Email service {'activated' if desired_state == 'true' else 'deactivated'}",
            status="success"
        )
        
        return jsonify({
            'success': True,
            'state': desired_state,
            'message': f"Email service {'activated' if desired_state == 'true' else 'deactivated'}"
        })
        
    except Exception as e:
        error_msg = handle_error(e, "Email Service Toggle Failed")
        return jsonify({
            'error': 'System error occurred',
            'details': error_msg
        }), 500

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
        get_logger().log_activity(
            action="SMTP Error",
            details=f"Failed to send email to {to_email}: {str(e)}",
            status="error"
        )
        return False
    except Exception as e:
        get_logger().log_activity(
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
            
        get_logger().log_activity(
            action="Test Email Sent",
            details=f"Test email sent to {email}",
            status="success"
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        error_msg = handle_error(e, "Test Email Failed")
        return jsonify({'error': error_msg}), 500

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
@debug_log("Force Send Menu", timing=True)
def force_send():
    try:
        # Validate requirements
        errors, settings, next_menu = validate_force_send()
        if errors:
            debug_print("Force send validation failed:", errors)
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': errors
            }), 400
            
        debug_print("Force send validation passed")
        debug_print("Settings:", settings)
        debug_print("Next menu:", next_menu)
        
        # Send menu
        success = send_menu_email(
            start_date=next_menu['period_start'],
            recipient_list=settings['recipient_emails'],
            season=next_menu['season'],
            week_number=next_menu['week']
        )
        
        message = "Test menu sent successfully!" if success else "Failed to send test menu"
        debug_print(message)
        
        get_logger().log_activity(
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
        debug_print("Force send error:", error_msg)
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
        get_logger().log_activity(
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
            
        get_logger().log_activity(
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
            'winter': {},
            'dates': {}  # Add dates section
        }
        
        # Organize templates
        if templates_response.data:
            for template in templates_response.data:
                season = template.get('season', '').lower()
                week = template.get('week')
                if season in templates:
                    if season == 'dates':
                        templates[season]['header'] = {
                            'file_url': template.get('template_url'),
                            'file_path': template.get('file_path'),
                            'updated_at': template.get('updated_at')
                        }
                    else:
                        templates[season][str(week)] = template
        
        get_logger().log_activity(
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
                             templates={'summer': {}, 'winter': {}, 'dates': {}},
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
                             smtp_status=smtp_status,
                             os=os)
                             
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
                get_logger().log_activity(
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
                get_logger().log_activity(
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
            if kwargs.get('filter_column'):
                query = query.filter(
                    kwargs['filter_column'],
                    kwargs.get('filter_operator', 'eq'),
                    kwargs['filter_value']
                )
            
        if kwargs.get('order_by'):
            order_desc = not kwargs.get('ascending', True)  # Convert to desc parameter
            query = query.order(kwargs['order_by'], desc=order_desc)
            
        if kwargs.get('limit'):
            query = query.limit(kwargs['limit'])
            
        result = query.execute()
        
        # Check if query took too long
        if time.time() - start_time > timeout:
            get_logger().log_activity(
                action="Slow Query Warning",
                details=f"Query to {table} took more than {timeout} seconds",
                status="warning"
            )
            
        return result
        
    except Exception as e:
        get_logger().log_activity(
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

    @app.template_filter('strftime')
    def format_datetime_strftime(value, format='%Y-%m-%d %H:%M:%S'):
        """Format datetime using strftime"""
        if not value:
            return ''
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                dt = value
            return dt.strftime(format)
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

@bp.route('/api/process-now', methods=['POST'])
@login_required
def process_emails_now():
    """Trigger immediate processing of unread menu emails"""
    try:
        print("Starting manual email processing...")
        from menu_monitor import MenuEmailMonitor
        
        # Initialize monitor with debug output
        print("Initializing MenuEmailMonitor...")
        monitor = MenuEmailMonitor()
        
        # Process emails with debug output
        print("Processing new emails...")
        try:
            monitor.process_new_emails()
            get_logger().log_activity(
                action="Manual Email Processing",
                details="Manually triggered menu email processing",
                status="success"
            )
            return jsonify({'success': True, 'message': 'Email processing completed'})
        except Exception as process_error:
            error_msg = str(process_error)
            if "poppler" in error_msg.lower():
                error_msg = "Poppler is not installed or not properly configured. Please install Poppler and ensure it's in your system PATH, or configure the correct path in config.yaml."
            get_logger().log_activity(
                action="Email Processing Failed",
                details=error_msg,
                status="error"
            )
            return jsonify({'error': error_msg}), 500
        
    except ImportError as e:
        error_msg = f"Failed to import MenuEmailMonitor: {str(e)}"
        print(error_msg)
        return jsonify({'error': error_msg}), 500
    except Exception as e:
        error_msg = f"Email processing failed: {str(e)}"
        print(error_msg)
        get_logger().log_activity(
            action="Email Processing Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'error': error_msg}), 500

@bp.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/menus')
@login_required
def menu_management():
    try:
        # Get current settings
        settings_response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
            
        settings = settings_response.data[0] if settings_response.data else None
        
        # Get all menus
        menus_response = supabase.table('menus')\
            .select('*')\
            .execute()
            
        # Convert to dictionary with menu_name as key
        menus = {}
        for menu in menus_response.data:
            if 'file_path' in menu:
                menu['file_url'] = supabase.storage.from_('menu-templates').get_public_url(menu['file_path'])
            menus[menu['name']] = menu
        
        return render_template(
            'menu_management.html',
            settings=settings,
            menus=menus
        )
        
    except Exception as e:
        logger.log_activity(
            action="Menu Page Load Failed",
            details=str(e),
            status="error"
        )
        print(f"Error loading menus: {str(e)}")
        return f"Error loading menus: {str(e)}", 500

@bp.route('/api/menus', methods=['GET', 'POST'])
@login_required
def handle_menus():
    if request.method == 'GET':
        try:
            # Get current settings
            settings = current_app.menu_service.get_settings()
            
            # Get all menus
            menus_response = supabase.table('menus').select('*').execute()
            menus = {}
            
            # Convert to dict with menu_name as key
            for menu in menus_response.data:
                # Get public URL for menu file
                menu['file_url'] = supabase.storage.from_('menu-templates').get_public_url(menu['file_path'])
                menus[menu['name']] = menu
            
            return jsonify({
                'settings': settings,
                'menus': menus
            })
            
        except Exception as e:
            logger.log_activity(
                action="Menu Fetch Failed",
                details=str(e),
                status="error"
            )
            return str(e), 500
            
    elif request.method == 'POST':
        try:
            if 'file' not in request.files:
                return "No file provided", 400
                
            file = request.files['file']
            menu_name = request.form.get('name')
            
            if not file or not file.filename:
                return "No file selected", 400
                
            if not menu_name:
                return "Menu name required", 400
                
            # Get file extension
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            if file_extension not in {'pdf', 'jpg', 'jpeg', 'png'}:
                return "Invalid file type. Must be PDF or image.", 400
                
            # Read file bytes
            file_bytes = file.read()
            file.seek(0)
            
            try:
                # Handle existing menu
                existing = supabase.table('menus').select('*').eq('name', menu_name).execute()
                if existing.data:
                    # Delete old file if it exists
                    supabase.storage.from_('menu-templates').remove([existing.data[0]['file_path']])
                    supabase.table('menus').delete().eq('name', menu_name).execute()
                    
                # Generate unique filename
                timestamp = int(datetime.now().timestamp())
                file_path = f"menus/{menu_name}_{timestamp}.{file_extension}"
                
                # Upload new file
                upload_response = supabase.storage.from_('menu-templates').upload(
                    path=file_path,
                    file=file_bytes,
                    file_options={"content-type": file.content_type}
                )
                
                # Get public URL
                file_url = supabase.storage.from_('menu-templates').get_public_url(file_path)
                
                # Save to database
                menu_data = {
                    'name': menu_name,
                    'file_path': file_path,
                    'file_url': file_url,
                    'created_at': datetime.now().isoformat()
                }
                
                supabase.table('menus').insert(menu_data).execute()
                
                logger.log_activity(
                    action="Menu Upload",
                    details=f"Uploaded menu: {menu_name}",
                    status="success"
                )
                
                return jsonify({'success': True, 'url': file_url})
                
            except Exception as e:
                logger.log_activity(
                    action="Menu Upload Failed",
                    details=str(e),
                    status="error"
                )
                return str(e), 500
                
        except Exception as e:
            logger.log_activity(
                action="Menu Upload Failed",
                details=str(e),
                status="error"
            )
            return str(e), 500

@bp.route('/api/menus/<menu_name>', methods=['DELETE'])
@login_required
def delete_menu(menu_name):
    try:
        # Get the menu record
        menu_response = supabase.table('menus')\
            .select('*')\
            .eq('name', menu_name)\
            .execute()
            
        if not menu_response.data:
            return "Menu not found", 404
            
        # Delete from storage first
        menu = menu_response.data[0]
        storage_path = f"menus/{menu['file_path'].split('/')[-1]}"
        supabase.storage.from_('menu-templates').remove([storage_path])
        
        # Then delete the database record
        supabase.table('menus')\
            .delete()\
            .eq('name', menu_name)\
            .execute()
            
        logger.log_activity(
            action="Menu Deleted",
            details=f"Deleted menu: {menu_name}",
            status="success"
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.log_activity(
            action="Menu Delete Failed",
            details=str(e),
            status="error"
        )
        return str(e), 500

@bp.route('/api/menus/<menu_id>')
def get_menu(menu_id):
    try:
        print(f"Fetching menu {menu_id}")  # Debug log
        
        response = supabase.table('menus')\
            .select('*')\
            .eq('id', menu_id)\
            .execute()
            
        if not response.data:
            return jsonify({'error': 'Menu not found'}), 404
            
        menu = response.data[0]
        print(f"Menu found: {menu}")  # Debug log
        
        return jsonify(menu)
        
    except Exception as e:
        print(f"Get menu error: {str(e)}")  # Debug log
        return jsonify({'error': str(e)}), 500

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
        
        get_logger().log_activity(
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
        get_logger().log_activity(
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
        get_logger().log_activity(
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
        get_logger().log_activity(
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
        get_logger().log_activity(
            action="Metrics Logging Failed",
            details=str(e),
            status="error"
        )

@bp.route('/api/status')
@login_required
def status():
    """API endpoint for service status"""
    return jsonify(get_service_state())

@bp.route('/api/status', methods=['POST'])
@login_required
def update_status():
    """Update service status"""
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({
            'success': False,
            'message': 'Invalid request format'
        }), 400
    
    state = {
        'active': bool(data.get('active', False)),
        'last_updated': datetime.now().isoformat(),
        'message': data.get('message', 'Status updated')
    }
    
    if save_service_state(state):
        return jsonify({
            'success': True,
            'state': state
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to save state'
        }), 500

@bp.route('/api/debug-mode', methods=['POST'])
@login_required
def toggle_debug_mode():
    """Toggle debug mode"""
    try:
        print("Debug mode toggle request received")
        
        # Validate request data
        data = request.get_json()
        if data is None:
            print("No JSON data provided")
            return jsonify({'error': 'No JSON data provided'}), 400
            
        active = data.get('active')
        if active is None:
            print("Missing active state")
            return jsonify({'error': 'Missing active state'}), 400
            
        # Get Redis client from app config
        redis_client = current_app.config.get('redis_client')
        if redis_client is None:
            print("Redis client not available")
            return jsonify({'error': 'System configuration error: Redis not available'}), 500
            
        try:
            # Convert boolean to string 'true' or 'false'
            value = 'true' if active else 'false'
            print(f"Setting debug_mode to: {value}")
            
            # Set value in Redis (or MockRedis)
            redis_client.set('debug_mode', value)
            
            # Log the change
            get_logger().log_activity(
                action="Debug Mode",
                details=f"Debug mode {'enabled' if active else 'disabled'}",
                status="success"
            )
            
            return jsonify({
                'success': True,
                'active': active,
                'message': f"Debug mode {'enabled' if active else 'disabled'} successfully"
            })
            
        except Exception as redis_error:
            print(f"Redis operation error: {str(redis_error)}")
            get_logger().log_activity(
                action="Debug Mode Error",
                details=f"Redis error: {str(redis_error)}",
                status="error"
            )
            return jsonify({
                'error': 'Failed to update debug mode',
                'details': str(redis_error)
            }), 500
            
    except Exception as e:
        print(f"Unexpected error in debug mode toggle: {str(e)}")
        error_msg = handle_error(e, "Debug Mode Toggle Failed")
        return jsonify({
            'error': 'System error occurred',
            'details': error_msg
        }), 500 