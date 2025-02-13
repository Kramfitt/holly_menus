from datetime import datetime
from typing import Optional, Dict, Any
import traceback
from flask import current_app

class Logger:
    def __init__(self):
        self.db = None
        
    def _get_db(self):
        """Get database connection lazily"""
        if not self.db:
            try:
                from config import supabase
                self.db = supabase
            except ImportError:
                print("Warning: Could not import supabase")
                return None
        return self.db
        
    def log_activity(self, action: str, details: Any, status: str = "info") -> bool:
        """Log an activity to the database"""
        try:
            db = self._get_db()
            if not db:
                print(f"Logging to console: {action} - {details}")
                return False
                
            # Create log entry
            log_entry = {
                'action': action,
                'details': details if isinstance(details, str) else str(details),
                'status': status,
                'created_at': datetime.now().isoformat()
            }
            
            # Insert into database
            db.table('activity_log').insert(log_entry).execute()
            
            # Print to console in debug mode
            if current_app and current_app.debug:
                print(f"[{status.upper()}] {action}: {details}")
                
            return True
            
        except Exception as e:
            print(f"Error logging activity: {str(e)}")
            print(f"Failed log entry: {action} - {details}")
            print(traceback.format_exc())
            return False
            
    def get_recent_activity(self, limit=10):
        """Get recent activity logs"""
        try:
            db = self._get_db()
            if not db:
                return []
                
            response = db.table('activity_log')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
                
            return response.data
            
        except Exception as e:
            print(f"Failed to get activity logs: {str(e)}")
            return []

# Global logger instance
_logger = None

def get_logger() -> Logger:
    """Get or create the global logger instance"""
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger

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