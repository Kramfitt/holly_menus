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
    state_file = '/opt/render/project/src/service_state.txt'  # Inside the project directory
    print(f"\n📂 Dashboard checking:")
    print(f"- State file path: {state_file}")
    print(f"- File exists? {os.path.exists(state_file)}")
    print(f"- Current directory: {os.getcwd()}")
    print(f"- Directory contents: {os.listdir('/')}")
    print(f"- /opt contents: {os.listdir('/opt')}")
    print(f"- /opt/render/project/src contents: {os.listdir('/opt/render/project/src')}")
    
    # Create state file if it doesn't exist
    if not os.path.exists(state_file):
        print(f"Creating initial state file at: {state_file}")
        try:
            with open(state_file, 'w') as f:
                f.write('false')  # Start paused
            os.chmod(state_file, 0o666)  # Allow read/write
            print("✅ Initial state file created")
        except Exception as e:
            print(f"❌ Failed to create state file: {str(e)}")
    
    # Read current state
    current_state = read_state_file()
    state = {
        "active": current_state,
        "last_updated": datetime.now() if os.path.exists(state_file) else None
    }
    return render_template('dashboard.html', state=state)

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
    state_file = '/opt/render/project/src/service_state.txt'
    print(f"\n🔄 TOGGLE REQUEST at {datetime.now()}")
    
    try:
        # Read current state
        current_state = read_state_file()
        new_state = not current_state
        
        # Write new state
        success = write_state_file(new_state)
        
        # Log the result
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"💡 Toggle: {current_state} → {new_state} [{status}]")
        
        if success:
            return jsonify({'status': 'success', 'state': str(new_state).lower()})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to write state'})
            
    except Exception as e:
        print(f"❌ Toggle error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True) 