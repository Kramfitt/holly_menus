from app.services import MenuService, EmailService

class MenuScheduler:
    def __init__(self):
        self.menu_service = MenuService()
        self.email_service = EmailService()

    def check_and_send(self):
        """Single entry point for scheduled tasks"""
        pass 