from flask import Flask, render_template, jsonify, request, session, redirect, url_for, Blueprint, current_app
from functools import wraps
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time
import redis
import psycopg2
from supabase import create_client, Client
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
from app.utils.logger import Logger
from app.utils.notifications import NotificationManager
from app.utils.backup import BackupManager
from worker import calculate_next_menu, send_menu_email
from config import supabase, redis_client, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
import pytz  # Add this import
from app.services.menu_service import MenuService
from app.services.email_service import EmailService

# Load environment variables
load_dotenv()

app = Flask(__name__)

bp = Blueprint('main', __name__)

# Make timedelta available to templates
@bp.context_processor
def utility_processor():
    return {
        'timedelta': timedelta,
        'datetime': datetime
    }

# Config from environment variables
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY'),
    STATE_FILE=os.getenv('STATE_FILE'),
    ADMIN_EMAIL=os.getenv('ADMIN_EMAIL'),
    SMTP_SERVER=os.getenv('SMTP_SERVER'),
    SMTP_PORT=int(os.getenv('SMTP_PORT')) if os.getenv('SMTP_PORT') else None,
    SMTP_USERNAME=os.getenv('SMTP_USERNAME'),
    SMTP_PASSWORD=os.getenv('SMTP_PASSWORD'),
    RECIPIENT_EMAILS=os.getenv('RECIPIENT_EMAILS', '').split(',') if os.getenv('RECIPIENT_EMAILS') else [],
    DASHBOARD_PASSWORD=os.getenv('DASHBOARD_PASSWORD')
)

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
notifications = NotificationManager()
backup_manager = BackupManager()

# Initialize services
menu_service = MenuService(db=supabase, storage=supabase.storage)
email_service = EmailService(config={
    'SMTP_SERVER': SMTP_SERVER,
    'SMTP_PORT': SMTP_PORT,
    'SMTP_USERNAME': SMTP_USERNAME,
    'SMTP_PASSWORD': SMTP_PASSWORD
})

def get_service_state():
    if not os.path.exists(app.config['STATE_FILE']):
        return {"active": True, "last_updated": None}
    
    with open(app.config['STATE_FILE'], 'r') as f:
        active = f.read().strip() == 'True'
        return {
            "active": active,
            "last_updated": datetime.fromtimestamp(os.path.getmtime(app.config['STATE_FILE']))
        }

def save_service_state(active):
    with open(app.config['STATE_FILE'], 'w') as f:
        f.write(str(active))

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            if request.form['password'] == current_app.config['DASHBOARD_PASSWORD']:
                session['logged_in'] = True
                return redirect(url_for('main.index'))
            return render_template('login.html', error='Invalid password')
        except Exception as e:
            logger.log_activity(
                action="Login Failed",
                details=str(e),
                status="error"
            )
            return render_template('login.html', error='Login error occurred')
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('main.login'))

@bp.route('/')
@login_required
def index():
    try:
        # Debug prints
        print("Starting index route...")
        
        # Use the menu service to get data
        print("Calculating next menu...")
        next_menu = menu_service.calculate_next_menu()
        print(f"Next menu: {next_menu}")
        
        # Get recent activity
        print("Fetching recent activity...")
        activity_response = supabase.table('activity_log')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()
            
        print(f"Activity response: {activity_response.data}")
        
        recent_activity = []
        for activity in activity_response.data or []:
            if 'created_at' in activity:
                activity['created_at'] = datetime.fromisoformat(
                    activity['created_at'].replace('Z', '+00:00')
                )
            recent_activity.append(activity)
        
        print(f"Processed activity: {recent_activity}")
        
        # Get service state
        service_active = redis_client.get('service_state') == b'true'
        print(f"Service active: {service_active}")
        
        # Try rendering with minimal data first
        return render_template('index.html',
                             next_menu=next_menu,
                             recent_activity=recent_activity,
                             service_active=service_active)
                             
    except Exception as e:
        import traceback
        print(f"❌ Dashboard error details:")
        print(traceback.format_exc())
        return f"Error loading dashboard: {str(e)}", 500

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
    if request.method == 'POST':
        try:
            data = request.json
            required = ['start_date', 'days_in_advance', 'recipient_emails']
            if not all(key in data for key in required):
                return jsonify({'error': 'Missing required fields'}), 400

            # Insert new settings
            settings = {
                'start_date': data['start_date'],
                'days_in_advance': int(data['days_in_advance']),
                'recipient_emails': data['recipient_emails'],
                'created_at': datetime.now().isoformat()
            }
            
            response = supabase.table('menu_settings').insert(settings).execute()
            
            logger.log_activity(
                action="Settings Updated",
                details="Menu settings updated successfully",
                status="success"
            )
            return jsonify({'success': True})
            
        except Exception as e:
            logger.log_activity(
                action="Settings Update Failed",
                details=str(e),
                status="error"
            )
            return jsonify({'error': str(e)}), 500
    else:
        try:
            settings = get_menu_settings()
            return jsonify(settings if settings else {})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@bp.route('/api/notifications/<notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    try:
        notifications.mark_as_read(notification_id)
        return "OK"
    except Exception as e:
        return str(e), 500

@bp.route('/api/notifications/read-all', methods=['POST'])
def mark_all_notifications_read():
    try:
        response = supabase.table('notifications')\
            .update({'read': True})\
            .eq('read', False)\
            .execute()
        return "OK"
    except Exception as e:
        return str(e), 500

@bp.route('/backup')
def backup_page():
    backups = backup_manager.get_backups()
    return render_template('backup.html', backups=backups)

@bp.route('/api/backup', methods=['POST'])
def create_backup():
    try:
        description = request.json.get('description')
        backup = backup_manager.create_backup(description)
        if backup:
            return jsonify({"status": "success", "backup": backup})
        return jsonify({"status": "error", "message": "Backup failed"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/backup/<backup_id>/restore', methods=['POST'])
def restore_backup(backup_id):
    try:
        success = backup_manager.restore_from_backup(backup_id)
        if success:
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Restore failed"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/api/menus', methods=['POST'])
@login_required
def upload_menu():
    try:
        print("Starting file upload...")  # Debug log
        
        if 'file' not in request.files:
            logger.log_activity(
                action="Menu Upload Failed",
                details="No file provided in request",
                status="error"
            )
            return "No file provided", 400
            
        file = request.files['file']
        menu_name = request.form.get('name')
        
        print(f"Received file upload request for menu: {menu_name}")  # Debug log
        
        if not file or not menu_name:
            logger.log_activity(
                action="Menu Upload Failed",
                details="Missing file or menu name",
                status="error"
            )
            return "Missing required fields", 400
            
        # Read the file into bytes
        try:
            file_bytes = file.stream.read()
            file_extension = file.filename.split('.')[-1].lower()
            print(f"File read successfully, size: {len(file_bytes)} bytes")  # Debug log
        except Exception as e:
            logger.log_activity(
                action="Menu Upload Failed",
                details=f"Error reading file: {str(e)}",
                status="error"
            )
            return f"Error reading file: {str(e)}", 500
        
        try:
            # Handle existing menu
            print("Checking for existing menu...")  # Debug log
            existing = supabase.table('menus').select('*').eq('name', menu_name).execute()
            if existing.data:
                print(f"Found existing menu: {existing.data[0]}")  # Debug log
                # Delete old file if it exists
                supabase.storage.from_('menus').remove([existing.data[0]['file_path']])
                supabase.table('menus').delete().eq('name', menu_name).execute()
        except Exception as e:
            logger.log_activity(
                action="Menu Upload Failed",
                details=f"Error handling existing menu: {str(e)}",
                status="error"
            )
            return f"Error handling existing menu: {str(e)}", 500
        
        try:
            # Generate unique filename
            timestamp = int(datetime.now().timestamp())
            file_path = f"menus/{menu_name}_{timestamp}.{file_extension}"
            print(f"Generated file path: {file_path}")  # Debug log
            
            # Upload new file
            print("Uploading file to storage...")  # Debug log
            upload_response = supabase.storage.from_('menus').upload(
                path=file_path,
                file=file_bytes,
                file_options={"content-type": file.content_type}
            )
            print(f"Storage upload response: {upload_response}")  # Debug log
        except Exception as e:
            logger.log_activity(
                action="Menu Upload Failed",
                details=f"Error uploading to storage: {str(e)}",
                status="error"
            )
            return f"Error uploading to storage: {str(e)}", 500
        
        try:
            # Create database record
            print("Creating database record...")  # Debug log
            db_response = supabase.table('menus').insert({
                'name': menu_name,
                'file_path': file_path,
                'uploaded_at': datetime.now().isoformat()
            }).execute()
            print(f"Database insert response: {db_response}")  # Debug log
        except Exception as e:
            # If database insert fails, try to clean up the uploaded file
            try:
                supabase.storage.from_('menus').remove([file_path])
            except:
                pass
            
            logger.log_activity(
                action="Menu Upload Failed",
                details=f"Error creating database record: {str(e)}",
                status="error"
            )
            return f"Error creating database record: {str(e)}", 500
        
        logger.log_activity(
            action="Menu Uploaded",
            details=f"Menu {menu_name} uploaded successfully",
            status="success"
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.log_activity(
            action="Menu Upload Failed",
            details=f"Unexpected error: {str(e)}",
            status="error"
        )
        print(f"❌ Upload error: {str(e)}")  # Debug print
        return str(e), 500

@bp.route('/api/menus/<menu_name>', methods=['DELETE'])
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
        supabase.storage.from_('menus').remove([storage_path])
        
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

@bp.route('/api/menus', methods=['GET'])
def get_menus():
    try:
        response = supabase.table('menus')\
            .select('*')\
            .order('name')\
            .execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

@bp.route('/menus')
@login_required
def menus():
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
            
        menus = menus_response.data if menus_response.data else []
        
        return render_template('menus.html', settings=settings, menus=menus)
        
    except Exception as e:
        logger.log_activity(
            action="Menu Page Load Failed",
            details=str(e),
            status="error"
        )
        return render_template('menus.html', error=str(e))

@bp.route('/api/next-menu')
def get_next_menu():
    try:
        settings_response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
            
        settings = settings_response.data[0] if settings_response.data else None
        
        if not settings:
            return jsonify({'error': 'Please configure menu settings first'})
            
        # Calculate next menu using worker logic
        next_menu = menu_service.calculate_next_menu()
        
        # Get menu names for the period
        menu_names = []
        if next_menu['menu_pair'] == "1_2":
            menu_names = [f"{next_menu['season']}Week1", f"{next_menu['season']}Week2"]
        else:
            menu_names = [f"{next_menu['season']}Week3", f"{next_menu['season']}Week4"]
            
        # Get menu URLs
        menus = []
        for name in menu_names:
            menu_response = supabase.table('menus')\
                .select('*')\
                .ilike('name', f'{name}%')\
                .execute()
                
            if menu_response.data:
                menus.append({
                    'name': menu_response.data[0]['name'],
                    'url': menu_response.data[0]['file_url']
                })
        
        return jsonify({
            'send_date': next_menu['send_date'].strftime('%Y-%m-%d'),
            'period_start': next_menu['period_start'].strftime('%Y-%m-%d'),
            'season': next_menu['season'].title(),
            'menu_pair': next_menu['menu_pair'],
            'menus': menus
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def register_filters(app):
    @app.template_filter('strftime')
    def strftime_filter(date, format='%Y-%m-%d'):
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        return date.strftime(format)

    @app.template_filter('datetime')
    def format_datetime(value):
        """Format datetime consistently across the app"""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                return value
        if isinstance(value, datetime):
            return value.strftime('%d %b %Y %H:%M')
        return value

    @app.template_filter('date')
    def format_date(value):
        """Format date consistently across the app"""
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                return value
        if isinstance(value, datetime):
            value = value.date()
        return value.strftime('%d %B %Y')

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
            
        next_menu = menu_service.calculate_next_menu()
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
    """Get latest menu settings from database"""
    try:
        response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
            
        settings = None
        if response.data:
            settings = response.data[0]
            # Convert ISO format datetime strings to datetime objects
            if 'created_at' in settings:
                settings['created_at'] = datetime.fromisoformat(
                    settings['created_at'].replace('Z', '+00:00')
                )
            if 'start_date' in settings:
                settings['start_date'] = datetime.strptime(
                    settings['start_date'], '%Y-%m-%d'
                ).date()
            if 'season_change_date' in settings:
                settings['season_change_date'] = datetime.strptime(
                    settings['season_change_date'], '%Y-%m-%d'
                ).date()
        return settings
        
    except Exception as e:
        logger.log_activity(
            action="Settings Error",
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
            app.config.get('SMTP_SERVER'),
            app.config.get('SMTP_PORT'),
            app.config.get('SMTP_USERNAME'),
            app.config.get('SMTP_PASSWORD')
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
        # Delete all entries except the clear action itself
        supabase.table('activity_log').delete().execute()
        
        # Log the clear action
        logger.log_activity(
            action="Activity Log Cleared",
            details="Activity log cleared by user",
            status="success"
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.log_activity(
            action="Clear Log Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'error': str(e)}), 500

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
            
        settings = settings_response.data[0] if settings_response.data else None
        
        # Get all menu templates
        menus_response = supabase.table('menus')\
            .select('*')\
            .execute()
            
        menus = menus_response.data if menus_response.data else []
        
        # Organize menus by season and week
        organized_menus = {
            'summer': {str(i): None for i in range(1, 5)},
            'winter': {str(i): None for i in range(1, 5)}
        }
        
        for menu in menus:
            if menu['season'] and menu['week']:
                organized_menus[menu['season']][str(menu['week'])] = menu
        
        return render_template('settings.html', 
                             settings=settings,
                             menus=organized_menus)
        
    except Exception as e:
        logger.log_activity(
            action="Settings Page Load Failed",
            details=str(e),
            status="error"
        )
        return render_template('settings.html', error=str(e))

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

if __name__ == '__main__':
    app.run(debug=True) 