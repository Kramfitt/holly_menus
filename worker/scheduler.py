from datetime import datetime
import time
from typing import Optional
from app.services.menu_service import MenuService
from app.services.email_service import EmailService
from app.utils.logger import Logger

class MenuScheduler:
    def __init__(self, menu_service: MenuService, email_service: EmailService, logger: Logger):
        self.menu_service = menu_service
        self.email_service = email_service
        self.logger = logger
        self.last_check: Optional[datetime] = None
        
    def run(self, check_interval: int = 300):
        """Run the scheduler with better error handling and logging"""
        self.logger.log("Scheduler", "Starting menu scheduler", level="info")
        
        while True:
            try:
                self._check_and_send()
                time.sleep(check_interval)
            except Exception as e:
                self.logger.log(
                    "Scheduler Error",
                    f"Error in scheduler loop: {str(e)}",
                    status="error",
                    level="error"
                )
                time.sleep(60)  # Wait before retrying
    
    def _check_and_send(self):
        """Check if menu needs to be sent with proper error handling"""
        try:
            now = datetime.now()
            self.last_check = now
            
            # Get next menu details
            next_menu = self.menu_service.calculate_next_menu()
            if not next_menu:
                return
                
            # Check if it's time to send
            if self._should_send_menu(next_menu):
                self._send_menu(next_menu)
                
        except Exception as e:
            self.logger.log(
                "Menu Check Error",
                str(e),
                status="error",
                level="error"
            )

    def _should_send_menu(self, next_menu):
        """Determine if menu should be sent now"""
        now = datetime.now().date()
        return (
            next_menu.get('send_date') == now and
            not self._already_sent_today()
        )

    def _send_menu(self, next_menu):
        """Send the menu with proper error handling"""
        try:
            # Get menu template
            menu_data = self.menu_service.get_menu_template(
                next_menu['season'], 
                next_menu['week']
            )
            
            if not menu_data:
                self.logger.log(
                    "Menu Send Failed",
                    "Menu template not found",
                    status="error",
                    level="error"
                )
                return
                
            # Send email
            success, error = self.email_service.send_menu(
                menu_data=menu_data,
                recipients=next_menu['recipient_emails'],
                start_date=next_menu['period_start'],
                menu_type=f"{next_menu['season']} Week {next_menu['week']}"
            )
            
            if success:
                self.logger.log(
                    "Menu Sent",
                    f"Menu sent successfully for {next_menu['period_start']}",
                    status="success"
                )
            else:
                self.logger.log(
                    "Menu Send Failed",
                    error or "Unknown error",
                    status="error"
                )
                
        except Exception as e:
            self.logger.log(
                "Menu Send Error",
                str(e),
                status="error",
                level="error"
            )

    def _already_sent_today(self):
        # Implementation of _already_sent_today method
        pass 