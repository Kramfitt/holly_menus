from flask import Flask, render_template, jsonify, request, session, redirect, url_for
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
from utils.logger import ActivityLogger
from utils.notifications import NotificationManager
from utils.backup import BackupManager
from worker import calculate_next_menu, send_menu_email
from config import supabase, redis_client, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
import pytz  # Add this import

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Make timedelta available to templates
@app.context_processor
def utility_processor():
    return {
        'timedelta': timedelta
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

logger = ActivityLogger()
notifications = NotificationManager()
backup_manager = BackupManager()

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
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == app.config['DASHBOARD_PASSWORD']:
            session['logged_in'] = True
            return redirect(url_for('index'))
        return 'Invalid password'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    try:
        # Get current settings
        settings = get_menu_settings()
        
        # Initialize next_menu as None
        next_menu = None
        
        if settings:
            try:
                next_menu = calculate_next_menu()
                if next_menu and 'send_date' in next_menu:  # Check if next_menu exists and has send_date
                    # Process dates if they exist
                    if isinstance(next_menu['period_start'], str):
                        next_menu['period_start'] = datetime.strptime(
                            next_menu['period_start'], '%Y-%m-%d'
                        ).date()
                    if isinstance(next_menu['send_date'], str):
                        next_menu['send_date'] = datetime.strptime(
                            next_menu['send_date'], '%Y-%m-%d'
                        ).date()
                    
                    # Calculate week number
                    start_date = settings['start_date']
                    weeks_since_start = (next_menu['period_start'] - start_date).days // 7
                    next_menu['week'] = (weeks_since_start % 4) + 1
            except Exception as e:
                logger.log_activity(
                    action="Menu Calculation",
                    details=f"Error calculating next menu: {str(e)}",
                    status="error"
                )
                next_menu = None  # Reset to None on error
        
        # Get recent activity
        print("Fetching recent activity...")  # Debug log
        activity_response = supabase.table('activity_log')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()
            
        print(f"Activity response: {activity_response.data}")  # Debug log
            
        recent_activity = []
        for activity in activity_response.data or []:
            if 'created_at' in activity:
                activity['created_at'] = datetime.fromisoformat(
                    activity['created_at'].replace('Z', '+00:00')
                )
            recent_activity.append(activity)
        
        print(f"Processed activity: {recent_activity}")  # Debug log
        
        # Get service state
        service_active = redis_client.get('service_state') == b'true'
        
        return render_template('index.html',
                             settings=settings,
                             next_menu=next_menu,
                             recent_activity=recent_activity,
                             service_active=service_active)
                             
    except Exception as e:
        logger.log_activity(
            action="Dashboard Error",
            details=str(e),
            status="error"
        )
        print(f"❌ Dashboard error: {str(e)}")  # Add debug print
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/preview')
@login_required
def preview():
    # Get current settings with proper season
    settings = get_menu_settings()  # Use the same function we use elsewhere
    
    # Get next menu details
    next_menu = calculate_next_menu()  # This will have the correct season
    
    # Get all menus with proper file URLs
    menus_response = supabase.table('menus')\
        .select('*')\
        .execute()
        
    all_menus = menus_response.data if menus_response.data else []
    
    # Make sure file_url is set for each menu
    for menu in all_menus:
        if 'file_path' in menu:
            menu['file_url'] = supabase.storage.from_('menus').get_public_url(menu['file_path'])
    
    return render_template(
        'preview.html',
        settings=settings,
        next_menu=next_menu,
        menus=all_menus
    )

# Add API endpoint for preview rendering
@app.route('/api/preview', methods=['GET'])
def api_preview_menu():
    try:
        menu_id = request.args.get('menu_id')
        preview_date = request.args.get('date')
        date_obj = datetime.strptime(preview_date, '%Y-%m-%d')
        
        # Get menu data
        response = supabase.table('menus')\
            .select('*')\
            .eq('id', menu_id)\
            .single()\
            .execute()
            
        if not response.data:
            return "Menu not found", 404
            
        menu = response.data
        
        # For PDFs, just return the viewer
        if menu['file_type'] == 'pdf':
            return f'<embed src="{menu["file_url"]}" type="application/pdf" width="100%" height="600px">'
            
        # Download and process image
        img_response = requests.get(menu['file_url'])
        img = Image.open(io.BytesIO(img_response.content))
        draw = ImageDraw.Draw(img)
        
        # Create font
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 25)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 25)
            except:
                try:
                    font = ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 25)
                except:
                    font = ImageFont.load_default()
        
        # Position settings from successful test
        x_start = 320
        y_start = 200
        x_spacing = 280
        
        # Add dates
        for day in range(7):
            x = x_start + (x_spacing * day)
            y = y_start
            current_date = date_obj + timedelta(days=day)
            date_text = current_date.strftime('%a %d\n%b')
            
            # Get text size for background
            bbox = draw.textbbox((x, y), date_text, font=font)
            padding_x = 20
            padding_y = 15
            
            # Calculate box dimensions
            box_width = bbox[2] - bbox[0] + (padding_x * 2)
            box_height = (bbox[3] - bbox[1] + (padding_y * 2)) * 0.8
            
            # Draw background
            draw.rectangle([
                bbox[0] - padding_x,
                bbox[1] - padding_y,
                bbox[0] + box_width - padding_x,
                bbox[1] + box_height - padding_y
            ], fill='white')
            
            # Draw text
            draw.text((x, y), date_text, fill='black', font=font)
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format=img.format)
        img_byte_arr = img_byte_arr.getvalue()
        
        # Generate preview path
        preview_path = f"previews/preview_{menu_id}_{preview_date}.{menu['file_type']}"
        
        try:
            # Try to delete existing preview
            supabase.storage.from_('menus').remove([preview_path])
        except:
            pass  # Ignore if file doesn't exist
        
        # Upload new preview
        supabase.storage.from_('menus').upload(
            preview_path,
            img_byte_arr,
            {'content-type': f"image/{menu['file_type']}"}
        )
        
        # Get preview URL
        preview_url = supabase.storage.from_('menus').get_public_url(preview_path)
        
        return f'<img src="{preview_url}?t={datetime.now().timestamp()}" class="img-fluid" alt="Menu Preview">'
            
    except Exception as e:
        print(f"❌ Preview error: {str(e)}")
        return f"Failed to generate preview: {str(e)}", 500

@app.route('/api/template', methods=['POST'])
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

@app.route('/api/template/<id>', methods=['DELETE'])
def delete_template(id):
    try:
        # Get file info from database
        response = supabase.table('menus')\
            .select('name')\
            .eq('id', id)\
            .single()\
            .execute()
            
        if response.data:
            filename = response.data['name']
            
            # Delete from storage
            supabase.storage.from_('menus').remove([f"menus/{filename}"])
            
            # Delete from database
            supabase.table('menus')\
                .delete()\
                .eq('id', id)\
                .execute()
            
            print(f"✅ Deleted: {filename}")
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Template not found'})
            
    except Exception as e:
        print(f"❌ Delete error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/system-check')
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

@app.route('/api/send-menu', methods=['POST'])
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

@app.route('/api/settings', methods=['POST'])
def update_settings():
    try:
        settings = request.json
        
        # Validate settings
        required_fields = ['start_date', 'season', 'days_in_advance', 'recipient_emails']
        for field in required_fields:
            if field not in settings:
                return f"Missing required field: {field}", 400
                
        # Save to database
        response = supabase.table('menu_settings').insert(settings).execute()
        
        logger.log_activity(
            action="Settings Updated",
            details="Menu settings updated successfully",
            status="success"
        )
        
        return jsonify(response.data[0])
        
    except Exception as e:
        logger.log_activity(
            action="Settings Update Failed",
            details=str(e),
            status="error"
        )
        return str(e), 500

@app.route('/api/notifications/<notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    try:
        notifications.mark_as_read(notification_id)
        return "OK"
    except Exception as e:
        return str(e), 500

@app.route('/api/notifications/read-all', methods=['POST'])
def mark_all_notifications_read():
    try:
        response = supabase.table('notifications')\
            .update({'read': True})\
            .eq('read', False)\
            .execute()
        return "OK"
    except Exception as e:
        return str(e), 500

@app.route('/backup')
def backup_page():
    backups = backup_manager.get_backups()
    return render_template('backup.html', backups=backups)

@app.route('/api/backup', methods=['POST'])
def create_backup():
    try:
        description = request.json.get('description')
        backup = backup_manager.create_backup(description)
        if backup:
            return jsonify({"status": "success", "backup": backup})
        return jsonify({"status": "error", "message": "Backup failed"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/backup/<backup_id>/restore', methods=['POST'])
def restore_backup(backup_id):
    try:
        success = backup_manager.restore_from_backup(backup_id)
        if success:
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Restore failed"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/menus', methods=['POST'])
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

@app.route('/api/menus/<menu_name>', methods=['DELETE'])
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

@app.route('/api/menus', methods=['GET'])
def get_menus():
    try:
        response = supabase.table('menus')\
            .select('*')\
            .order('name')\
            .execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/menus/<menu_id>')
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

@app.route('/menus')
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
                menu['file_url'] = supabase.storage.from_('menus').get_public_url(menu['file_path'])
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

@app.route('/api/next-menu')
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
        next_menu = calculate_next_menu()
        
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

@app.template_filter('strftime')
def strftime_filter(date, format='%Y-%m-%d'):
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d')
    return date.strftime(format)

@app.route('/api/email-status', methods=['GET'])
def get_email_status():
    try:
        state = redis_client.get('service_state')
        return jsonify({'active': state == b'true'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/toggle-email', methods=['POST'])
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

@app.route('/api/test-email', methods=['POST'])
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

@app.route('/api/debug-mode', methods=['GET', 'POST'])
@login_required
def debug_mode():
    if request.method == 'POST':
        active = request.json.get('active', False)
        redis_client.set('debug_mode', str(active).lower())
        
        logger.log_activity(
            action="Debug Mode",
            details=f"Debug mode {'enabled' if active else 'disabled'}",
            status="debug"
        )
        
        return jsonify({'active': active})
    else:
        is_debug = redis_client.get('debug_mode') == b'true'
        return jsonify({'active': is_debug})

@app.route('/api/force-send', methods=['POST'])
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

@app.route('/api/email-health', methods=['GET'])
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

@app.route('/api/clear-activity-log', methods=['POST'])
def clear_activity_log():
    try:
        # Delete ALL entries from activity_log table
        supabase.table('activity_log')\
            .delete()\
            .filter('id', 'not.is', 'null')\
            .execute()
            
        logger.log_activity(
            action="Activity Log Cleared",
            details="All activity log entries were cleared",
            status="success"
        )
        
        return jsonify({'success': True})
    except Exception as e:
        logger.log_activity(
            action="Clear Log Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'success': False, 'error': str(e)}), 500

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

# Add this near the top with other template filters
@app.template_filter('datetime')
def format_datetime(value):
    """Format a datetime object or ISO string."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    if isinstance(value, datetime):
        # Make timestamp more readable
        return value.strftime('%d %b %Y %H:%M')  # e.g., "11 Feb 2025 20:28"
    return value

if __name__ == '__main__':
    app.run(debug=True) 