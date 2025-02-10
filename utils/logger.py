from datetime import datetime
import logging
from supabase import create_client
import os

class ActivityLogger:
    def __init__(self):
        self.supabase = create_client(
            os.getenv("SUPABASE_URL", ''),
            os.getenv("SUPABASE_KEY", '')
        )
        
    def log_activity(self, action, details=None, status='success'):
        """Log activity to both file and database"""
        try:
            # Log to database
            self.supabase.table('activity_log').insert({
                'action': action,
                'details': details,
                'status': status
            }).execute()
            
            # Log to file
            level = {
                'success': logging.INFO,
                'warning': logging.WARNING,
                'error': logging.ERROR
            }.get(status, logging.INFO)
            
            logging.log(level, f"{action}: {details}")
            
        except Exception as e:
            logging.error(f"Failed to log activity: {str(e)}")
            
    def get_recent_activity(self, limit=10):
        """Get recent activity logs"""
        try:
            response = self.supabase.table('activity_log')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
                
            return response.data
            
        except Exception as e:
            logging.error(f"Failed to get activity logs: {str(e)}")
            return [] 