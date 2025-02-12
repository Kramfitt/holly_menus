from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class MenuService:
    def __init__(self, db, storage):
        self.db = db
        self.storage = storage
        
    def calculate_next_menu(self) -> Dict[str, Any]:
        """Calculate which menu should be sent next"""
        try:
            settings = self.get_settings()
            if not settings:
                return self._create_response(None, "No menu settings found")
                
            today = datetime.now().date()
            
            # Calculate next menu start date (2 weeks from now)
            next_date = today + timedelta(days=14)
            
            # Determine season
            season = self._determine_season(next_date, settings)
            
            # Calculate week number (1-4)
            weeks_since_start = ((next_date - settings['start_date']).days // 14)
            week_number = (weeks_since_start % 4) + 1
            
            # Calculate send date
            send_date = next_date - timedelta(days=settings['days_in_advance'])
            
            menu_details = {
                'send_date': send_date,
                'period_start': next_date,
                'season': season,
                'week': week_number,
                'menu_pair': f"{week_number}_" + str(week_number + 1 if week_number % 2 == 1 else week_number - 1),
                'recipient_emails': settings['recipient_emails']
            }
            
            return self._create_response(menu_details)
            
        except Exception as e:
            return self._create_response(None, str(e))
    
    def get_settings(self) -> Optional[Dict[str, Any]]:
        """Get current menu settings"""
        try:
            response = self.db.table('menu_settings')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
                
            if not response.data:
                return None
                
            settings = response.data[0]
            
            # Convert date strings to date objects
            settings['start_date'] = datetime.strptime(
                settings['start_date'], '%Y-%m-%d'
            ).date()
            
            if settings.get('season_change_date'):
                settings['season_change_date'] = datetime.strptime(
                    settings['season_change_date'], '%Y-%m-%d'
                ).date()
                
            return settings
            
        except Exception as e:
            print(f"Error getting settings: {str(e)}")
            return None
    
    def _determine_season(self, date: datetime.date, settings: Dict[str, Any]) -> str:
        """Determine the season for a given date"""
        if not settings.get('season_change_date'):
            return settings['season']
            
        current_season = settings['season']
        change_date = settings['season_change_date']
        
        # Convert string date to datetime if needed
        if isinstance(change_date, str):
            change_date = datetime.strptime(change_date, '%Y-%m-%d').date()
        
        if date >= change_date:
            return 'winter' if current_season == 'summer' else 'summer'
            
        return current_season
    
    def _create_response(self, data: Optional[Dict[str, Any]], error: Optional[str] = None) -> Dict[str, Any]:
        """Create a standardized response format"""
        return {
            'data': data,
            'error': error,
            'success': data is not None
        }

    def get_menu_template(self):
        """Handle menu template retrieval"""
        pass 