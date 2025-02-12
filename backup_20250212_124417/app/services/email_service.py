class EmailService:
    def __init__(self, config):
        self.config = config
        
    def send_menu(self, menu_data, recipients):
        """Send menu with better error handling"""
        try:
            if not self._validate_menu(menu_data):
                return False, "Invalid menu data"
                
            email = self._create_menu_email(menu_data, recipients)
            return self._send_email(email)
            
        except Exception as e:
            return False, str(e)

    def _validate_menu(self, menu_data):
        # Implementation of _validate_menu method
        pass

    def _create_menu_email(self, menu_data, recipients):
        # Implementation of _create_menu_email method
        pass

    def _send_email(self, email):
        # Implementation of _send_email method
        pass 