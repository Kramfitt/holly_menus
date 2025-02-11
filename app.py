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
from worker import calculate_next_menu  # Import the function

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Config from environment variables
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'dev-key-please-change'),
    STATE_FILE=os.getenv('STATE_FILE', 'service_state.txt'),
    ADMIN_EMAIL=os.getenv('ADMIN_EMAIL', 'default@example.com'),
    SMTP_SERVER=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
    SMTP_PORT=int(os.getenv('SMTP_PORT', '587')),
    SMTP_USERNAME=os.getenv('SMTP_USERNAME', ''),
    SMTP_PASSWORD=os.getenv('SMTP_PASSWORD', ''),
    RECIPIENT_EMAILS=os.getenv('RECIPIENT_EMAILS', '').split(','),
    DASHBOARD_PASSWORD=os.getenv('DASHBOARD_PASSWORD', 'change-this-password')
)

# Near the top with other configs
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url)

# Initialize Supabase client
supabase = create_client(
    os.getenv("SUPABASE_URL", ''),
    os.getenv("SUPABASE_KEY", '')
)

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
            return redirect(url_for('home'))
        return 'Invalid password'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    try:
        # Get current settings
        settings = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
            
        # Get menu count
        menus = supabase.table('menus')\
            .select('*')\
            .execute()
            
        # Calculate next menu
        next_menu = None
        if settings.data:
            current_settings = settings.data[0]
            next_menu = calculate_next_menu()
            
        # Get recent activity
        recent_activity = logger.get_recent_activity(limit=5)
        
        # Format dates if needed
        if recent_activity:
            for activity in recent_activity:
                if isinstance(activity['created_at'], str):
                    activity['created_at'] = datetime.fromisoformat(
                        activity['created_at'].replace('Z', '+00:00')
                    )
        
        # Get unread notifications
        unread_notifications = notifications.get_unread_notifications()
        
        return render_template('index.html',
                             settings=settings.data[0] if settings.data else None,
                             next_menu=next_menu,
                             menu_count=len(menus.data) if menus.data else 0,
                             recent_activity=recent_activity,
                             unread_notifications=unread_notifications)
                             
    except Exception as e:
        logger.log_activity(
            action="Dashboard Error",
            details=str(e),
            status="error"
        )
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/preview')
def preview():
    try:
        print("Starting preview route...")  # Debug log
        
        # Get latest settings
        settings_response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
            
        settings = settings_response.data[0] if settings_response.data else None
        print("Settings loaded:", settings)  # Debug log
        
        # Get all menus
        menus_response = supabase.table('menus')\
            .select('*')\
            .order('name', desc=False)\
            .execute()
            
        # Calculate preview date (2 weeks from now)
        preview_date = datetime.now() + timedelta(days=14)
        
        # Only calculate next menu if we have valid settings
        next_menu = None
        if settings:
            try:
                print("Processing dates...")  # Debug log
                # Use today's date if start_date is empty or invalid
                if not settings.get('start_date'):
                    print("No start date, using today")  # Debug log
                    settings['start_date'] = datetime.now().strftime('%Y-%m-%d')
                
                print("Start date:", settings.get('start_date'))  # Debug log
                print("Summer start:", settings.get('summer_start'))  # Debug log
                print("Winter start:", settings.get('winter_start'))  # Debug log
                
                # Ensure we have valid dates
                today = datetime.now()
                current_year = today.year
                
                # Set default dates if missing
                if not settings.get('summer_start'):
                    settings['summer_start'] = f"{current_year}-12-01"
                if not settings.get('winter_start'):
                    settings['winter_start'] = f"{current_year}-06-01"
                
                try:
                    # Validate date formats
                    datetime.strptime(settings['start_date'], '%Y-%m-%d')
                    datetime.strptime(settings['summer_start'], '%Y-%m-%d')
                    datetime.strptime(settings['winter_start'], '%Y-%m-%d')
                    
                    next_menu = calculate_next_menu()
                except ValueError as date_error:
                    print(f"Date parsing error: {date_error}")  # Debug log
                    raise
                    
            except Exception as e:
                logger.log_activity(
                    action="Preview Calculation Failed",
                    details=str(e),
                    status="warning"
                )
                print(f"Preview calculation error: {str(e)}")  # Debug log
        else:
            print("No settings found")  # Debug log
        
        return render_template('preview.html', 
                             menus=menus_response.data,
                             preview_date=preview_date,
                             settings=settings,
                             next_menu=next_menu)
                             
    except Exception as e:
        logger.log_activity(
            action="Preview Load Failed",
            details=str(e),
            status="error"
        )
        print(f"Preview Error: {str(e)}")  # Debug log
        return f"Error loading preview: {str(e)}", 500

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

def send_menu_email(menu_id, start_date, recipient_list):
    try:
        # Get menu data
        response = supabase.table('menus')\
            .select('*')\
            .eq('id', menu_id)\
            .single()\
            .execute()
            
        if not response.data:
            return "Menu not found", 404
            
        menu = response.data
        
        # Generate preview image
        preview_date = start_date.strftime('%Y-%m-%d')
        preview_path = f"previews/preview_{menu_id}_{preview_date}.{menu['file_type']}"
        
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
            
        result = send_menu_email(menu_id, date, recipients)
        return result
        
    except Exception as e:
        print(f"❌ Send menu error: {str(e)}")
        return f"Failed to send menu: {str(e)}", 500

@app.route('/api/settings', methods=['POST'])
def save_settings():
    try:
        data = request.json
        print("Incoming settings data:", data)  # Debug log
        
        # Handle empty dates
        if 'summer_start' in data:
            if not data['summer_start']:
                data['summer_start'] = None
            else:
                try:
                    if isinstance(data['summer_start'], str):
                        if 'T' in data['summer_start']:
                            data['summer_start'] = data['summer_start'].split('T')[0]
                        date_obj = datetime.strptime(data['summer_start'], '%Y-%m-%d')
                        data['summer_start'] = date_obj.isoformat()
                except Exception as e:
                    print(f"Error parsing summer_start: {e}")
                    data['summer_start'] = None
                    
        if 'winter_start' in data:
            if not data['winter_start']:
                data['winter_start'] = None
            else:
                try:
                    if isinstance(data['winter_start'], str):
                        if 'T' in data['winter_start']:
                            data['winter_start'] = data['winter_start'].split('T')[0]
                        date_obj = datetime.strptime(data['winter_start'], '%Y-%m-%d')
                        data['winter_start'] = date_obj.isoformat()
                except Exception as e:
                    print(f"Error parsing winter_start: {e}")
                    data['winter_start'] = None
            
        print("Processed settings data:", data)  # Debug log
            
        response = supabase.table('menu_settings').insert(data).execute()
        
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
        return jsonify({'error': str(e)}), 500

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
def upload_menu():
    try:
        file = request.files['file']
        name = request.form['name']
        
        # Get file extension and create storage path
        file_ext = os.path.splitext(file.filename)[1]
        storage_path = f"{name}{file_ext}"  # Simplified path
        
        # Check if menu already exists in database
        existing = supabase.table('menus').select('*').eq('name', name).execute()
        if existing.data:
            return jsonify({'error': 'Menu with this name already exists'}), 400
            
        # Try to delete from storage first (in case file exists but no DB record)
        try:
            supabase.storage.from_('menus').remove([storage_path])
        except:
            pass  # Ignore errors if file doesn't exist
            
        # Upload to storage
        file_data = file.read()
        supabase.storage.from_('menus').upload(
            path=storage_path,
            file=file_data,
            file_options={"content-type": file.content_type}
        )
        
        # Get public URL
        file_url = supabase.storage.from_('menus').get_public_url(storage_path)
        
        # Save to database
        menu_data = {
            'name': name,
            'file_path': storage_path,
            'file_type': file_ext[1:],  # Remove the dot
            'url': file_url
        }
        
        result = supabase.table('menus').insert(menu_data).execute()
        
        logger.log_activity(
            action="Menu Uploaded",
            details=f"Menu {name} uploaded successfully",
            status="success"
        )
        
        return jsonify(result.data[0])
        
    except Exception as e:
        logger.log_activity(
            action="Menu Upload Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'error': str(e)}), 500

@app.route('/api/menus/<menu_id>', methods=['DELETE'])
def delete_menu(menu_id):
    try:
        # Get menu details first
        menu = supabase.table('menus').select('*').eq('id', menu_id).execute()
        if not menu.data:
            return jsonify({'error': 'Menu not found'}), 404
            
        menu_data = menu.data[0]
        
        # Delete from storage first
        storage_path = f"menus/{menu_data['name']}"
        supabase.storage.from_('menus').remove([storage_path])
        
        # Then delete from database
        supabase.table('menus').delete().eq('id', menu_id).execute()
        
        # Log the deletion
        logger.log_activity(
            action="Menu Deleted",
            details=f"Menu {menu_data['name']} deleted successfully",
            status="success"
        )
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.log_activity(
            action="Menu Delete Failed",
            details=str(e),
            status="error"
        )
        return jsonify({'error': str(e)}), 500

@app.route('/api/menus', methods=['GET'])
def get_menus():
    try:
        response = supabase.table('menus')\
            .select('*')\
            .order('name', desc=False)\
            .execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 