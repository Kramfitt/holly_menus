from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from functools import wraps
import os
from datetime import datetime
from dotenv import load_dotenv

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

@app.route('/toggle', methods=['POST'])
@login_required
def toggle_service():
    state = get_service_state()
    new_state = not state['active']
    save_service_state(new_state)
    
    # Add status message
    status = "RESUMED" if new_state else "PAUSED"
    print(f"Service {status} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)
    
    return jsonify({
        "active": new_state,
        "message": f"Service has been {status}"
    })

if __name__ == '__main__':
    app.run(debug=True) 