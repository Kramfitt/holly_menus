from flask import Flask, jsonify
from config import (
    supabase, 
    redis_client, 
    SMTP_SERVER, 
    SMTP_PORT, 
    SMTP_USERNAME, 
    SMTP_PASSWORD
)
from app.services.menu_service import MenuService
from app.services.email_service import EmailService
from app.utils.logger import Logger
import os
from datetime import datetime

# Create the Flask application
app = Flask(__name__,
           template_folder='templates',  # Make sure this exists
           static_folder='static')       # And this for static files

# Add secret key
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')

# Initialize services
app.menu_service = MenuService(db=supabase, storage=supabase.storage)
app.email_service = EmailService(config={
    'SMTP_SERVER': SMTP_SERVER,
    'SMTP_PORT': SMTP_PORT,
    'SMTP_USERNAME': SMTP_USERNAME,
    'SMTP_PASSWORD': SMTP_PASSWORD
})
app.logger = Logger()

# Import and register routes and filters
from app.routes.main import bp as main_bp, register_filters
app.register_blueprint(main_bp)
register_filters(app)  # Register template filters

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'database': bool(supabase),
            'redis': bool(redis_client),
            'worker': True
        }
    })
