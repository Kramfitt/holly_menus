from flask import Flask
from config import (
    supabase, 
    redis_client, 
    SMTP_SERVER, 
    SMTP_PORT, 
    SMTP_USERNAME, 
    SMTP_PASSWORD,
    SECRET_KEY,
    DASHBOARD_PASSWORD
)
from app.services.menu_service import MenuService
from app.services.email_service import EmailService
from app.utils.logger import Logger
import os
from datetime import datetime

# Create the Flask application
app = Flask(__name__)

# Add configuration
app.config.update(
    SECRET_KEY=SECRET_KEY,
    DASHBOARD_PASSWORD=DASHBOARD_PASSWORD
)

# Print config for debugging (remove in production)
print("Configuration loaded:")
print(f"- SECRET_KEY set: {'Yes' if app.config.get('SECRET_KEY') else 'No'}")
print(f"- DASHBOARD_PASSWORD set: {'Yes' if app.config.get('DASHBOARD_PASSWORD') else 'No'}")

# Initialize services
app.menu_service = MenuService(db=supabase, storage=supabase.storage)
app.email_service = EmailService(config={
    'SMTP_SERVER': SMTP_SERVER,
    'SMTP_PORT': SMTP_PORT,
    'SMTP_USERNAME': SMTP_USERNAME,
    'SMTP_PASSWORD': SMTP_PASSWORD
})
app.logger = Logger()

# Import and register routes
from app.routes.main import bp as main_bp
app.register_blueprint(main_bp)

@app.route('/health')
def health_check():
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'dashboard_password_set': bool(app.config.get('DASHBOARD_PASSWORD')),
            'secret_key_set': bool(app.config.get('SECRET_KEY'))
        },
        'services': {
            'database': bool(supabase),
            'redis': bool(redis_client),
            'worker': True
        }
    }

if __name__ == "__main__":
    app.run()