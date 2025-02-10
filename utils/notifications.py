from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

class NotificationManager:
    def __init__(self):
        self.supabase = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self.admin_email = os.getenv("ADMIN_EMAIL")
        
    def create_notification(self, type, message, details=None):
        """Create a new notification"""
        try:
            response = self.supabase.table('notifications').insert({
                'type': type,
                'message': message,
                'details': details
            }).execute()
            
            # If it's an error, send email to admin
            if type == 'error':
                self.send_admin_email(message, details)
                
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Failed to create notification: {str(e)}")
            return None
            
    def send_admin_email(self, message, details=None):
        """Send email notification to admin"""
        try:
            msg = MIMEMultipart()
            msg['From'] = os.getenv("SMTP_USERNAME")
            msg['To'] = self.admin_email
            msg['Subject'] = f"Menu System Alert: {message}"
            
            body = f"""
            Alert from Menu System
            
            Type: Error
            Message: {message}
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Details:
            {details if details else 'No additional details'}
            
            Please check the system status page for more information.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as server:
                server.starttls()
                server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
                server.send_message(msg)
                
        except Exception as e:
            print(f"Failed to send admin email: {str(e)}")
            
    def get_unread_notifications(self):
        """Get all unread notifications"""
        try:
            response = self.supabase.table('notifications')\
                .select('*')\
                .eq('read', False)\
                .order('created_at', desc=True)\
                .execute()
                
            return response.data
            
        except Exception as e:
            print(f"Failed to get notifications: {str(e)}")
            return []
            
    def mark_as_read(self, notification_id):
        """Mark a notification as read"""
        try:
            self.supabase.table('notifications')\
                .update({'read': True})\
                .eq('id', notification_id)\
                .execute()
                
        except Exception as e:
            print(f"Failed to mark notification as read: {str(e)}") 