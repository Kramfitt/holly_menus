from flask import Flask
from config import supabase, redis_client, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
from app.services.menu_service import MenuService
from app.services.email_service import EmailService
from app.utils.logger import Logger

def create_app():
    app = Flask(__name__)
    
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
    
    return app
