from datetime import datetime

class MenuService:
    def __init__(self, db, storage):
        self.db = db
        self.storage = storage
        
    def calculate_next_menu(self):
        """Calculate next menu with better error handling"""
        try:
            settings = self.get_settings()
            if not settings:
                return self._create_response(None, "No menu settings found")
                
            today = datetime.now().date()
            menu_details = self._calculate_menu_details(settings, today)
            
            return self._create_response(menu_details)
            
        except Exception as e:
            return self._create_response(None, str(e))
            
    def _create_response(self, data, error=None):
        return {
            'data': data,
            'error': error,
            'success': data is not None
        }

    def get_menu_template(self):
        """Handle menu template retrieval"""
        pass 