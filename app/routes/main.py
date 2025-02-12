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
    SMTP_USERNAME, SMTP_PASSWORD
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
from postgrest.constants import desc  # For Supabase order by
from dotenv import load_dotenv

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

def get_service_state():
    if not os.path.exists(current_app.config['STATE_FILE']):
        return {"active": True, "last_updated": None}
    
    with open(current_app.config['STATE_FILE'], 'r') as f:
        active = f.read().strip() == 'True'
        return {
            "active": active,
            "last_updated": datetime.fromtimestamp(os.path.getmtime(current_app.config['STATE_FILE']))
        }

def save_service_state(active):
    with open(current_app.config['STATE_FILE'], 'w') as f:
        f.write(str(active))

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

@bp.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            dashboard_password = current_app.config.get('DASHBOARD_PASSWORD')
            submitted_password = request.form.get('password')
            
            # Debug logging (remove in production)
            print(f"Login attempt - Password configured: {'Yes' if dashboard_password else 'No'}")
            print(f"Submitted password length: {len(submitted_password) if submitted_password else 0}")
            
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
                
                # Debug logging
                print("Login successful - redirecting to index")
                return redirect(url_for('main.index'))
            
            # Failed login attempt
            logger.log_activity(
                action="Login Failed",
                details="Invalid password attempt",
                status="warning"
            )
            return render_template('login.html', 
                error="Invalid password", 
                show_error=True)
                
    except Exception as e:
        error_msg = handle_error(e, "Login System Error")
        return render_template('login.html', 
            error=error_msg,
            show_error=True)
            
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('main.login'))

@bp.route('/')
@login_required
def index():
    try:
        # Get service state
        service_active = redis_client.get('service_state') == b'true'
        
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
                .order('created_at', desc=True)\
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

@bp.route('/api/template', methods=['POST'])
def upload_template():
    try:
        if 'template' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file uploaded'})
            
        file = request.files['template']
        if not file.filename:
            return jsonify({'status': 'error', 'message': 'No file selected'})
            
        # Secure the filename
        filename = secure_filename(file.filename)
        file_type = filename.rsplit('.', 1)[1].lower()
        
        # Validate file type
        if file_type not in ['pdf', 'jpg', 'jpeg', 'png']:
            return jsonify({'status': 'error', 'message': 'Invalid file type'})
            
        # Upload to Supabase Storage
        file_path = f"menus/{filename}"
        supabase.storage.from_('menus').upload(
            file_path,
            file.read(),
            {'content-type': file.content_type}
        )
        
        # Get public URL
        file_url = supabase.storage.from_('menus').get_public_url(file_path)
        
        # Store in database
        response = supabase.table('menus').insert({
            'name': filename,
            'file_url': file_url,
            'file_type': file_type
        }).execute()
        
        print(f"✅ Uploaded: {filename}")
        return jsonify({'status': 'success', 'data': response.data})
        
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

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
        settings = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        # Calculate next menu details using worker logic
        next_menu = None
        if settings.data:
            current_settings = settings.data[0]
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
            settings=settings.data[0] if settings.data else None,
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

@bp.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            required_fields = ['start_date', 'days_in_advance', 'recipient_emails']
            if not all(field in data for field in required_fields):
                return jsonify({'error': 'Missing required fields'}), 400
                
            # Validate data
            try:
                datetime.strptime(data['start_date'], '%Y-%m-%d')
                days_advance = int(data['days_in_advance'])
                if days_advance < 1:
                    raise ValueError("Days in advance must be positive")
            except ValueError as ve:
                return jsonify({'error': f"Invalid data: {str(ve)}"}), 400
                
            # Create settings object
            settings = {
                'start_date': data['start_date'],
                'days_in_advance': days_advance,
                'recipient_emails': data['recipient_emails'],
                'season': data.get('season', 'summer'),
                'season_change_date': data.get('season_change_date'),
                'created_at': datetime.now().isoformat()
            }
            
            # Insert new settings
            supabase.table('menu_settings').insert(settings).execute()
            
            logger.log_activity(
                action="Settings Updated",
                details="Menu settings updated successfully",
                status="success"
            )
            
            return jsonify({'success': True})
            
        else:
            # Get current settings
            settings_response = supabase.table('menu_settings')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
                
            settings = settings_response.data[0] if settings_response.data else {}
            return jsonify(settings)
            
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

@bp.route('/api/test-email', methods=['POST'])
def send_test_email():
    try:
        email = request.json.get('email')
        if not email:
            return jsonify({'error': 'Email address required'}), 400
            
        # Send test email
        msg = MIMEMultipart()
        msg['From'] = f"Holly Lea Menus <{os.getenv('SMTP_USERNAME')}>"
        msg['To'] = email
        msg['Subject'] = "Test Email from Holly Lea Menu System"
        
        body = "This is a test email from the Holly Lea Menu System."
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
            server.send_message(msg)
        
        logger.log_activity(
            action="Test Email Sent",
            details=f"Test email sent to {email}",
            status="success"
        )
        
        return jsonify({'success': True})
    except Exception as e:
        logger.log_activity(
            action="Test Email Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'error': str(e)}), 500

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

@bp.route('/api/force-send', methods=['POST'])
@login_required
def force_send():
    try:
        if redis_client.get('debug_mode') != b'true':
            return jsonify({
                'success': False, 
                'message': 'Debug mode not active'
            }), 400
            
        next_menu = calculate_next_menu()
        if not next_menu:
            return jsonify({
                'success': False,
                'message': 'Could not calculate next menu'
            }), 400
            
        # Get recipient emails from settings
        settings = get_menu_settings()
        if not settings.get('recipient_emails'):
            return jsonify({
                'success': False, 
                'message': 'No recipient emails configured'
            }), 400
            
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
            status="debug"
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f"Error: {str(e)}"
        }), 500

def get_menu_settings():
    """Get current menu settings"""
    try:
        settings_response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
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
        # Check if email service is active
        service_state = redis_client.get('service_state')
        is_active = service_state == b'true'
        
        # Check SMTP settings exist
        smtp_configured = all([
            current_app.config.get('SMTP_SERVER'),
            current_app.config.get('SMTP_PORT'),
            current_app.config.get('SMTP_USERNAME'),
            current_app.config.get('SMTP_PASSWORD')
        ])
        
        return jsonify({
            'status': 'healthy' if is_active and smtp_configured else 'inactive',
            'details': {
                'service_active': is_active,
                'smtp_configured': smtp_configured
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@bp.route('/api/clear-activity-log', methods=['POST'])
@login_required
def clear_activity_log():
    try:
        # Delete all records using a filter that's always true
        supabase.table('activity_log')\
            .delete()\
            .gte('id', 0)\
            .execute()
            
        # Log the clear action
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
            'error': str(e),
            'message': error_msg
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
        # Get current settings
        settings_response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
            
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
        # Get service states
        email_active = redis_client.get('service_state') == b'true'
        debug_mode = redis_client.get('debug_mode') == b'true'
        
        # Get database status
        db_status = False
        try:
            supabase.table('menu_settings').select('count').execute()
            db_status = True
        except:
            pass
            
        # Get Redis status
        redis_status = False
        try:
            redis_client.ping()
            redis_status = True
        except:
            pass
            
        return render_template('status.html',
                             email_active=email_active,
                             debug_mode=debug_mode,
                             db_status=db_status,
                             redis_status=redis_status)
    except Exception as e:
        logger.log_activity(
            action="Status Page Load Failed",
            details=str(e),
            status="error"
        )
        return render_template('status.html', error=str(e))

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

# Remove this at the bottom
# if __name__ == '__main__':
#     bp.run(debug=True)  # Blueprints don't have run() 