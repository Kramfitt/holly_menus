from datetime import datetime
from typing import Literal, Optional
from config import supabase

class Logger:
    def __init__(self):
        self.db = supabase
        
    def log(self, 
            action: str, 
            details: str, 
            status: Literal['success', 'warning', 'error', 'debug'] = 'info',
            level: Literal['info', 'warning', 'error', 'debug'] = 'info'):
        """Enhanced logging with levels and database storage"""
        try:
            # Console logging
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] [{level.upper()}] {action}: {details}")
            
            # Database logging
            self.db.table('activity_log').insert({
                'action': action,
                'details': details,
                'status': status,
                'level': level,
                'created_at': datetime.now().isoformat()
            }).execute()
            
        except Exception as e:
            print(f"Logging failed: {str(e)}")

    def get_recent_activity(self, limit=10):
        """Get recent activity logs"""
        try:
            response = self.db.table('activity_log')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
                
            return response.data
            
        except Exception as e:
            print(f"Failed to get activity logs: {str(e)}")
            return [] 