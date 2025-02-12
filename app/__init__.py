from flask import Flask, jsonify
from datetime import datetime, timedelta
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

def create_app():
    """Application factory function"""
    app = Flask(__name__,
               template_folder='templates',
               static_folder='static')
    
    # Basic configuration
    app.config.update(
        DEBUG=False,  # Set to False for production
        SECRET_KEY=SECRET_KEY,
        DASHBOARD_PASSWORD=DASHBOARD_PASSWORD,
        
        # Session configuration
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax'
    )
    
    # Log configuration status
    app.logger.info(f"Configuration loaded:")
    app.logger.info(f"- SECRET_KEY set: {'Yes' if SECRET_KEY else 'No'}")
    app.logger.info(f"- DASHBOARD_PASSWORD set: {'Yes' if DASHBOARD_PASSWORD else 'No'}")
    
    # Initialize services
    app.menu_service = MenuService(db=supabase, storage=supabase.storage)
    app.email_service = EmailService(config={
        'SMTP_SERVER': SMTP_SERVER,
        'SMTP_PORT': SMTP_PORT,
        'SMTP_USERNAME': SMTP_USERNAME,
        'SMTP_PASSWORD': SMTP_PASSWORD
    })
    app.logger = Logger()
    
    # Register blueprints
    from app.routes.main import bp as main_bp, register_filters
    app.register_blueprint(main_bp)
    register_filters(app)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'config': {
                'secret_key_set': bool(SECRET_KEY),
                'dashboard_password_set': bool(DASHBOARD_PASSWORD),
                'debug_mode': app.debug
            },
            'services': {
                'database': bool(supabase),
                'redis': bool(redis_client),
                'worker': True
            }
        })
    
    return app

# Create the application instance
app = create_app()
