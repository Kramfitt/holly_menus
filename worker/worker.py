import os
from dotenv import load_dotenv
import sys
from datetime import datetime
import time
from app.services.menu_service import MenuService
from app.services.email_service import EmailService
from app.utils.logger import Logger
from config import (
    supabase, 
    redis_client, 
    SMTP_SERVER, 
    SMTP_PORT, 
    SMTP_USERNAME, 
    SMTP_PASSWORD
)

# Force load from .env file
load_dotenv(override=True)

def calculate_next_menu():
    """Calculate which menu should be sent next"""
    try:
        menu_service = MenuService(db=supabase, storage=supabase.storage)
        return menu_service.calculate_next_menu()
    except Exception as e:
        logger = Logger()
        logger.log_activity(
            action="Menu Calculation Error",
            details=str(e),
            status="error"
        )
        return None

def send_menu_email(start_date, recipient_list, season, week_number):
    """Send menu email"""
    try:
        email_service = EmailService(config={
            'SMTP_SERVER': SMTP_SERVER,
            'SMTP_PORT': SMTP_PORT,
            'SMTP_USERNAME': SMTP_USERNAME,
            'SMTP_PASSWORD': SMTP_PASSWORD
        })
        
        menu_service = MenuService(db=supabase, storage=supabase.storage)
        menu_data = menu_service.get_menu_template(season, week_number)
        
        if not menu_data:
            raise Exception(f"No template found for {season} week {week_number}")
            
        return email_service.send_menu(
            menu_data=menu_data,
            recipients=recipient_list,
            start_date=start_date,
            menu_type=f"{season} Week {week_number}"
        )
        
    except Exception as e:
        logger = Logger()
        logger.log_activity(
            action="Menu Send Error",
            details=str(e),
            status="error"
        )
        return False

def main():
    """Main worker process"""
    print("\n🚀 Worker service starting...")
    
    # Initialize services
    logger = Logger()
    menu_service = MenuService(db=supabase, storage=supabase.storage)
    email_service = EmailService(config={
        'SMTP_SERVER': SMTP_SERVER,
        'SMTP_PORT': SMTP_PORT,
        'SMTP_USERNAME': SMTP_USERNAME,
        'SMTP_PASSWORD': SMTP_PASSWORD
    })
    
    logger.log_activity(
        action="Worker Started",
        details="Menu worker service initialized",
        status="info"
    )
    
    while True:
        try:
            # Check if service is active
            is_active = redis_client.get('service_state') == b'true'
            is_debug = redis_client.get('debug_mode') == b'true'
            
            if is_active or is_debug:
                # Calculate next menu
                next_menu = menu_service.calculate_next_menu()
                if next_menu:
                    # Check if it's time to send
                    if datetime.now().date() == next_menu['send_date'] or is_debug:
                        logger.log_activity(
                            action="Menu Send Started",
                            details=f"Sending menu for {next_menu['period_start']}",
                            status="info"
                        )
                        # Send menu
                        success = email_service.send_menu(
                            menu_data=next_menu['menu_data'],
                            recipients=next_menu['recipient_emails'],
                            start_date=next_menu['period_start'],
                            menu_type=f"{next_menu['season']} Week {next_menu['week']}"
                        )
                        if success:
                            logger.log_activity(
                                action="Menu Sent",
                                details="Menu sent successfully",
                                status="success"
                            )
            
            # Sleep for 5 minutes
            time.sleep(300)
            
        except Exception as e:
            logger.log_activity(
                action="Worker Error",
                details=str(e),
                status="error"
            )
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main() 