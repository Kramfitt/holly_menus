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
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

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
@login_required
def home():
    try:
        # Read current state from Redis
        current_state = redis_client.get('service_state')
        is_active = current_state == b'true' if current_state else False
        
        state = {
            "active": is_active,
            "last_updated": datetime.now()
        }
        print(f"📊 Dashboard state: {'ACTIVE' if is_active else 'PAUSED'}")
        return render_template('dashboard.html', state=state)
    except Exception as e:
        print(f"❌ Redis error: {str(e)}")
        return render_template('dashboard.html', state={"active": False})

def write_state_file(state):
    """Write state file with verification"""
    state_file = '/opt/render/project/src/service_state.txt'
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        # Write state with explicit permissions
        with open(state_file, 'w') as f:
            state_str = str(state).lower()
            f.write(state_str)
            f.flush()
            os.fsync(f.fileno())
        
        # Set permissions to allow both services to read/write
        os.chmod(state_file, 0o666)
        
        print(f"✅ State file written: {state_str}")
        return True
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def read_state_file():
    """Read state file with retries"""
    state_file = '/opt/render/project/src/service_state.txt'
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if not os.path.exists(state_file):
                print(f"❌ State file missing (attempt {attempt + 1})")
                time.sleep(1)
                continue
                
            with open(state_file, 'r') as f:
                content = f.read().strip().lower()
                print(f"📄 Read state: '{content}' (attempt {attempt + 1})")
                return content == 'true'
                
        except Exception as e:
            print(f"❌ Error reading state: {str(e)} (attempt {attempt + 1})")
            time.sleep(1)
    
    print("❌ Failed to read state file after retries")
    return False  # Default to paused if can't read

@app.route('/toggle', methods=['POST'])
def toggle_service():
    try:
        # Get current state
        current_state = redis_client.get('service_state')
        current_state = current_state == b'true' if current_state else False
        
        # Toggle state
        new_state = not current_state
        redis_client.set('service_state', str(new_state).lower())
        
        print(f"💡 Toggle: {current_state} → {new_state}")
        return jsonify({'status': 'success', 'state': str(new_state).lower()})
            
    except Exception as e:
        print(f"❌ Toggle error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/preview', methods=['GET'])
@login_required
def preview_menu():
    try:
        # Get all menus
        response = supabase.table('menus')\
            .select('*')\
            .order('created_at', desc=True)\
            .execute()
        
        menus = response.data
        preview_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        return render_template('preview.html', 
                             menus=menus,
                             preview_date=preview_date)
                             
    except Exception as e:
        print(f"❌ Load error: {str(e)}")
        return render_template('preview.html', 
                             menus=[],
                             preview_date=datetime.now().strftime('%Y-%m-%d'),
                             error="Failed to load menus")

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
        # Check multiple possible locations
        tesseract_paths = [
            '/usr/bin/tesseract',
            '/usr/local/bin/tesseract',
            'tesseract'
        ]
        
        for path in tesseract_paths:
            try:
                version = subprocess.check_output([path, '--version'])
                return render_template('system_check.html',
                    tesseract_path=path,
                    tesseract_version=version.decode(),
                    path=os.environ.get('PATH'),
                    status='ok'
                )
            except:
                continue
                
        return render_template('system_check.html',
            error='Tesseract not found in any standard location',
            checked_paths=tesseract_paths,
            path=os.environ.get('PATH'),
            status='error'
        )
    except Exception as e:
        return render_template('system_check.html',
            error=str(e),
            path=os.environ.get('PATH'),
            status='error'
        )

if __name__ == '__main__':
    app.run(debug=True) 