from flask import Flask, jsonify, render_template
from datetime import datetime, timedelta
from config import (
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

def create_app():
    """Create and configure the Flask application"""
    try:
        app = Flask(__name__)
        
        # Load configuration first
        app.config.from_object('config')
        
        # Check required config before anything else
        missing_config = [key for key in REQUIRED_CONFIG if not app.config.get(key)]
        if missing_config:
            raise ValueError(f"Missing required configuration: {', '.join(missing_config)}")
        
        # Set session configuration
        app.config.update(
            PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax'
        )
        
        # Initialize services only after config check
        try:
            app.menu_service = MenuService(db=supabase, storage=supabase.storage)
            app.email_service = EmailService(config={
                'SMTP_SERVER': SMTP_SERVER,
                'SMTP_PORT': SMTP_PORT,
                'SMTP_USERNAME': SMTP_USERNAME,
                'SMTP_PASSWORD': SMTP_PASSWORD
            })
            app.logger = Logger()
        except Exception as service_error:
            raise RuntimeError(f"Failed to initialize services: {str(service_error)}")
        
        # Register blueprint and filters
        from app.routes.main import bp as main_bp, register_filters
        app.register_blueprint(main_bp)
        register_filters(app)
        
        # Configure logging last
        configure_logging(app)
        
        # Add service health checks
        check_services(app)
        
        # Verify app setup
        verify_app_setup(app)
        
        return app
        
    except Exception as e:
        # Log the error
        print(f"Error creating app: {str(e)}")
        traceback.print_exc()
        
        # Create minimal error app with better error handling
        error_app = Flask(__name__)
        
        @error_app.route('/')
        @error_app.route('/<path:path>')
        def error_page(path=None):
            if isinstance(e, ValueError):
                # Show config errors directly
                error_msg = str(e)
            elif isinstance(e, RuntimeError):
                # Show service initialization errors
                error_msg = f"Application initialization error: {str(e)}"
            else:
                # Generic error for everything else
                error_msg = "Application configuration error. Please contact administrator."
            
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
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Menu Dashboard startup')

def check_services(app):
    """Verify all services are working"""
    errors = []
    
    # Check Redis
    try:
        app.redis_client.ping()
    except Exception as e:
        errors.append(f"Redis connection failed: {str(e)}")
    
    # Check Database
    try:
        app.supabase.table('menu_settings').select('count').execute()
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
