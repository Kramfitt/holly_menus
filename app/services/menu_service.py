from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class MenuService:
    def __init__(self, db, storage):
        self.db = db
        self.storage = storage
        
    def calculate_next_menu(self):
        """Calculate which menu should be sent next"""
        try:
            # Get current settings
            settings_response = self.db.table('menu_settings')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()

            if not settings_response.data:
                print("No menu settings found")
                return None

            settings = settings_response.data[0]
            start_date = datetime.strptime(settings['start_date'], '%Y-%m-%d').date()
            today = datetime.now().date()

            # Calculate next menu period
            days_since_start = (today - start_date).days
            weeks_since_start = days_since_start // 7
            current_period = weeks_since_start // 2
            
            # Calculate next period start
            next_period_start = start_date + timedelta(weeks=current_period * 2)
            if today >= next_period_start:
                next_period_start += timedelta(weeks=2)

            # Calculate send date
            send_date = next_period_start - timedelta(days=settings['days_in_advance'])

            # Determine season and week
            season = settings['season']
            week_pair = "1_2" if (current_period % 2 == 0) else "3_4"

            return {
                'send_date': send_date,
                'period_start': next_period_start,
                'season': season,
                'menu_pair': week_pair
            }

        except Exception as e:
            print(f"Error calculating next menu: {str(e)}")
            return None
    
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