from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import smtplib
from typing import List, Tuple, Optional

class EmailService:
    def __init__(self, config):
        self.config = config
        
    def send_menu(self, menu_data: bytes, recipients: List[str], 
                  start_date: datetime.date, menu_type: str) -> Tuple[bool, Optional[str]]:
        """Send menu with better error handling"""
        try:
            if not self._validate_menu(menu_data):
                return False, "Invalid menu data"
                
            msg = self._create_menu_email(menu_data, recipients, start_date, menu_type)
            return self._send_email(msg)
            
        except Exception as e:
            return False, str(e)
    
    def _validate_menu(self, menu_data: bytes) -> bool:
        """Validate menu data"""
        if not menu_data:
            return False
        try:
            # Try to open as image to validate format
            from PIL import Image
            import io
            Image.open(io.BytesIO(menu_data))
            return True
        except Exception:
            return False
    
    def _create_menu_email(self, menu_data: bytes, recipients: List[str],
                          start_date: datetime.date, menu_type: str) -> MIMEMultipart:
        """Create the email message"""
        msg = MIMEMultipart()
        msg['From'] = self.config['SMTP_USERNAME']
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"Menu for week starting {start_date.strftime('%B %d, %Y')}"
        
        # Create HTML body
        html = self._create_html_body(start_date, menu_type)
        msg.attach(MIMEText(html, 'html'))
        
        # Attach menu image
        img_attachment = MIMEImage(menu_data)
        img_attachment.add_header('Content-Disposition', 'attachment', 
                                filename=f'menu_{start_date.strftime("%Y%m%d")}.png')
        msg.attach(img_attachment)
        
        return msg
    
    def _send_email(self, msg: MIMEMultipart) -> Tuple[bool, Optional[str]]:
        """Send the email"""
        try:
            with smtplib.SMTP(self.config['SMTP_SERVER'], self.config['SMTP_PORT']) as server:
                server.starttls()
                server.login(self.config['SMTP_USERNAME'], self.config['SMTP_PASSWORD'])
                server.send_message(msg)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _create_html_body(self, start_date: datetime.date, menu_type: str) -> str:
        """Create HTML email body"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #004d99; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Holly Lea Menu</h1>
                </div>
                <div class="content">
                    <p>Hello,</p>
                    <p>Please find attached the menu for the period starting {start_date.strftime('%B %d, %Y')}.</p>
                    <p>This is a {menu_type} menu.</p>
                    <p>Best regards,<br>Holly Lea Menu System</p>
                </div>
            </div>
        </body>
        </html>
        """ 