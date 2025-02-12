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

def create_app():
    """Create and configure the Flask application"""
    try:
        app = Flask(__name__)
        
        # Load configuration
        app.config.from_object('config')
        
        # Set session configuration first
        app.config.update(
            PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax'
        )
        
        # Use imported list
        missing_config = [key for key in REQUIRED_CONFIG if not app.config.get(key)]
        if missing_config:
            raise ValueError(f"Missing required configuration: {', '.join(missing_config)}")
            
        # Initialize services
        app.menu_service = MenuService(db=supabase, storage=supabase.storage)
        app.email_service = EmailService(config={
            'SMTP_SERVER': SMTP_SERVER,
            'SMTP_PORT': SMTP_PORT,
            'SMTP_USERNAME': SMTP_USERNAME,
            'SMTP_PASSWORD': SMTP_PASSWORD
        })
        app.logger = Logger()
        
        # Register blueprint and filters
        from app.routes.main import bp as main_bp, register_filters
        app.register_blueprint(main_bp)
        register_filters(app)
        
        configure_logging(app)
        
        return app
        
    except Exception as e:
        # Log the error
        print(f"Error creating app: {str(e)}")
        traceback.print_exc()
        
        # Create minimal error app
        error_app = Flask(__name__)
        
        @error_app.route('/')
        @error_app.route('/<path:path>')
        def error_page(path=None):
            error_msg = str(e) if isinstance(e, ValueError) else "Application configuration error. Please contact administrator."
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

# Create the application instance
app = create_app()
