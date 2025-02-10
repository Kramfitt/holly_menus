from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import time

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
    state = get_service_state()
    return render_template('dashboard.html', 
                         state=state,
                         config={
                             'admin_email': app.config['ADMIN_EMAIL'],
                             'recipients': app.config['RECIPIENT_EMAILS']
                         })

def write_state_file(state):
    """Write state file with verification"""
    state_file = '/opt/render/service_state.txt'
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            
            # Write new state
            with open(state_file, 'w') as f:
                f.write(str(state).lower())
                f.flush()
                os.fsync(f.fileno())
            
            # Verify write
            with open(state_file, 'r') as f:
                content = f.read().strip().lower()
                if content == str(state).lower():
                    print(f"✅ State written and verified: {content}")
                    return True
                    
            print(f"❌ Write verification failed (attempt {attempt + 1})")
            
        except Exception as e:
            print(f"❌ Error writing state: {str(e)} (attempt {attempt + 1})")
            time.sleep(1)
    
    return False

def read_state_file():
    """Read state file with retries"""
    state_file = '/opt/render/service_state.txt'
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
    print("\n🔄 Toggle request received")
    try:
        # Read current state
        print("1. Reading current state...")
        current_state = read_state_file()
        print(f"   Current state: {current_state}")
        
        # Toggle state
        new_state = not current_state
        print(f"2. New state will be: {new_state}")
        
        # Write new state
        print("3. Attempting to write new state...")
        if write_state_file(new_state):
            print("✅ Toggle successful!")
            return jsonify({'status': 'success', 'state': str(new_state).lower()})
        else:
            print("❌ Failed to write state")
            return jsonify({'status': 'error', 'message': 'Failed to write state'})
            
    except Exception as e:
        print(f"❌ Toggle error: {str(e)}")
        return jsonify({'status': 'error', 'message': f"Toggle failed: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True) 