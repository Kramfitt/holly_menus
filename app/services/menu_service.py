from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import time

class MenuService:
    def __init__(self, db, storage):
        self.db = db
        self.storage = storage
        self.bucket = 'menu-templates'
        
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

    def save_template(self, file, season, week):
        """Save menu template to storage and database"""
        try:
            # Generate unique filename
            filename = f"{season.lower()}_week{week}_{int(time.time())}.pdf"
            
            # Upload to storage
            file_path = f"{season}/{filename}"
            self.storage.from_(self.bucket).upload(file_path, file)
            
            # Get public URL
            file_url = self.storage.from_(self.bucket).get_public_url(file_path)
            
            # Save to database
            self.db.table('menu_templates').upsert({
                'season': season.lower(),
                'week': int(week),
                'template_url': file_url,
                'updated_at': datetime.now().isoformat()
            }).execute()
            
            return {'success': True, 'url': file_url}
            
        except Exception as e:
            return {'error': str(e)}

    def get_templates(self):
        """Get all templates organized by season"""
        try:
            response = self.db.table('menu_templates').select('*').execute()
            templates = {'summer': {}, 'winter': {}}
            
            for template in response.data:
                season = template['season']
                week = str(template['week'])
                templates[season][week] = {
                    'file_url': template['template_url'],
                    'updated_at': template['updated_at']
                }
            
            return templates
        except Exception as e:
            logger.error(f"Error fetching templates: {str(e)}")
            return {'summer': {}, 'winter': {}} 