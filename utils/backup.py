import json
from datetime import datetime
import os
from supabase import create_client

class BackupManager:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        
    def create_backup(self, description=None):
        """Create a backup of all system data"""
        try:
            # Get all data
            settings = self.supabase.table('menu_settings').select('*').execute()
            menus = self.supabase.table('menus').select('*').execute()
            
            # Create backup object
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'description': description,
                'data': {
                    'settings': settings.data,
                    'menus': menus.data
                }
            }
            
            # Save to backups table
            response = self.supabase.table('backups').insert({
                'data': backup_data,
                'description': description,
                'created_at': backup_data['timestamp']
            }).execute()
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Backup failed: {str(e)}")
            return None
            
    def restore_from_backup(self, backup_id):
        """Restore system from a backup"""
        try:
            # Get backup data
            backup = self.supabase.table('backups')\
                .select('*')\
                .eq('id', backup_id)\
                .execute()
                
            if not backup.data:
                raise Exception("Backup not found")
                
            backup_data = backup.data[0]['data']
            
            # Restore settings
            if backup_data['data']['settings']:
                latest_settings = backup_data['data']['settings'][-1]
                self.supabase.table('menu_settings').insert(latest_settings).execute()
            
            # Restore menus
            if backup_data['data']['menus']:
                for menu in backup_data['data']['menus']:
                    self.supabase.table('menus').insert(menu).execute()
                    
            return True
            
        except Exception as e:
            print(f"Restore failed: {str(e)}")
            return False
            
    def get_backups(self):
        """Get list of available backups"""
        try:
            response = self.supabase.table('backups')\
                .select('*')\
                .order('created_at', desc=True)\
                .execute()
                
            return response.data
            
        except Exception as e:
            print(f"Failed to get backups: {str(e)}")
            return [] 