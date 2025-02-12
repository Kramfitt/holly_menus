import os
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
            
            # Database logging - remove level field
            self.db.table('activity_log').insert({
                'action': action,
                'details': details,
                'status': status,
                'created_at': datetime.now().isoformat()
            }).execute()
            
        except Exception as e:
            print(f"Logging failed: {str(e)}")
            
    # Flask logger compatibility methods
    def error(self, msg, *args, **kwargs):
        self.log("Error", str(msg), status="error", level="error")
        
    def warning(self, msg, *args, **kwargs):
        self.log("Warning", str(msg), status="warning", level="warning")
        
    def info(self, msg, *args, **kwargs):
        self.log("Info", str(msg), status="info", level="info")
        
    def debug(self, msg, *args, **kwargs):
        self.log("Debug", str(msg), status="debug", level="debug")

    # Alias for backward compatibility
    log_activity = log

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