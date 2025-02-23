from flask import Flask, jsonify, render_template
from datetime import datetime, timedelta
from config import (  # Import from config package
    supabase, 
    redis_client, 
    SMTP_SERVER, 
    SMTP_PORT, 
    SMTP_USERNAME, 
    SMTP_PASSWORD,
    SECRET_KEY,
    DASHBOARD_PASSWORD,
    REQUIRED_CONFIG
)
from app.services.menu_service import MenuService
from app.services.email_service import EmailService
from app.utils.logger import Logger
import traceback
import logging
from logging.handlers import RotatingFileHandler
import os
import smtplib
from werkzeug.exceptions import HTTPException

def create_app():
    """Create and configure the Flask application"""
    error_info = None  # Store error info for error app
    
    try:
        app = Flask(__name__)
        
        # Configure app with all required settings
        app.config.update(
            SECRET_KEY=SECRET_KEY,
            DASHBOARD_PASSWORD=DASHBOARD_PASSWORD,
            SMTP_SERVER=SMTP_SERVER,
            SMTP_PORT=SMTP_PORT,
            SMTP_USERNAME=SMTP_USERNAME,
            SMTP_PASSWORD=SMTP_PASSWORD,
            SUPABASE_URL=os.getenv('SUPABASE_URL'),
            SUPABASE_KEY=os.getenv('SUPABASE_KEY'),
            SESSION_COOKIE_SECURE=False if os.getenv('FLASK_ENV') == 'development' else True,
            SESSION_COOKIE_HTTPONLY=True,
            PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
            FLASK_ENV=os.getenv('FLASK_ENV', 'production'),
            DEBUG=os.getenv('FLASK_DEBUG', '0') == '1'
        )
        
        # Verify required configuration
        missing_config = []
        for key, required in REQUIRED_CONFIG.items():
            if required and not app.config.get(key):
                missing_config.append(key)
        if missing_config:
            raise ValueError(f"Missing required configuration: {', '.join(missing_config)}")
        
        # Set up logging
        configure_logging(app)
        
        # Register blueprint
        from app.routes.main import bp as main_bp, register_filters
        app.register_blueprint(main_bp)
        
        # Register template filters
        register_filters(app)
        
        # Initialize services
        app.menu_service = MenuService(db=supabase, storage=supabase.storage)
        app.email_service = EmailService(config={
            'SMTP_SERVER': SMTP_SERVER,
            'SMTP_PORT': SMTP_PORT,
            'SMTP_USERNAME': SMTP_USERNAME,
            'SMTP_PASSWORD': SMTP_PASSWORD
        })
        
        # Verify services in production
        if app.config['FLASK_ENV'] != 'development':
            check_services(app)
        
        return app
        
    except Exception as e:
        # Log the error
        print(f"Error creating app: {str(e)}")
        traceback.print_exc()
        error_info = e
        
        # Create minimal error app
        error_app = Flask(__name__)
        
        @error_app.route('/')
        @error_app.route('/<path:path>')
        def error_page(path=None):
            if isinstance(error_info, ValueError):
                error_msg = str(error_info)
            elif isinstance(error_info, RuntimeError):
                error_msg = f"Application initialization error: {str(error_info)}"
            else:
                error_msg = f"Application configuration error: {str(error_info)}"
            return render_template('error.html', error=error_msg)
                
        return error_app

def configure_logging(app):
    """Configure logging for the application"""
    if not os.path.exists('logs'):
        os.mkdir('logs')
        
    file_handler = RotatingFileHandler(
        'logs/menu_dashboard.log',
        maxBytes=10240,
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'
    ))
    file_handler.setLevel(logging.INFO)
    
    # Use Flask's logger instead of our custom logger for system logging
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Menu Dashboard startup')
    
    # Initialize our custom activity logger
    app.activity_logger = Logger()

def check_services(app):
    """Verify all services are working"""
    errors = []
    
    # Check Redis using global client
    try:
        redis_client.ping()
    except Exception as e:
        errors.append(f"Redis connection failed: {str(e)}")
    
    # Check Database
    try:
        supabase.table('menu_settings').select('count').execute()
    except Exception as e:
        errors.append(f"Database connection failed: {str(e)}")
    
    # Check SMTP
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
    except Exception as e:
        errors.append(f"SMTP connection failed: {str(e)}")
    
    if errors:
        raise RuntimeError("\n".join(errors))

def verify_app_setup(app):
    """Verify critical app configuration"""
    if not app.secret_key:
        raise RuntimeError("Flask secret key not set")
        
    if not app.config.get('SESSION_COOKIE_SECURE'):
        app.logger.warning("Session cookies not set to secure")
        
    if not app.config.get('SESSION_COOKIE_HTTPONLY'):
        app.logger.warning("Session cookies not set to httponly")
        
    if not os.access('logs', os.W_OK):
        raise RuntimeError("Logs directory not writable")

# Create the application instance
app = create_app()
