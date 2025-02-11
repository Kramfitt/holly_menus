import os
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import time
import redis
from supabase import create_client
import logging
from email.mime.application import MIMEApplication
from utils.logger import ActivityLogger
from utils.notifications import NotificationManager
from config import supabase, redis_client, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
from PIL import Image, ImageDraw, ImageFont
import io

# Force load from .env file
load_dotenv(override=True)

# Near the top with other configs
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url)

# Set initial state if none exists
if redis_client.get('service_state') is None:
    print("📝 Setting initial Redis state to: false")
    redis_client.set('service_state', 'false')  # Start paused

# Instead, get SMTP settings directly from env:
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')

# Initialize logger and notifications
logger = ActivityLogger()
notifications = NotificationManager()

def should_send_emails():
    """Check if email service is active"""
    try:
        state = redis_client.get('service_state')
        debug = redis_client.get('debug_mode')
        
        is_active = state == b'true' if state else False
        is_debug = debug == b'true' if debug else False
        
        if is_debug:
            print("🔧 Running in DEBUG mode")
            
        return is_active
    except Exception as e:
        print(f"❌ Redis error: {str(e)}")
        return False  # Default to paused on error

def send_email():
    """Send email using settings from .env"""
    print(f"🔄 Worker PID {os.getpid()} attempting to send email")
    # Get settings
    recipients = os.getenv('RECIPIENT_EMAILS').split(',')
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = SMTP_USERNAME
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = "Menu Service Test"
    
    # Create message body versions
    body = f"This is a test email from the menu service."
    msg.attach(MIMEText(body, 'plain'))
    
    # HTML Email Template
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #004d99; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            .menu-details {{ background-color: #fff; padding: 15px; border-left: 4px solid #004d99; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Holly Lea Menu</h1>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>Please find attached the menu for the upcoming period.</p>
                
                <div class="menu-details">
                    <strong>Period:</strong><br>
                    {datetime.now().strftime('%d %B %Y')} - 
                    {(datetime.now() + timedelta(days=13)).strftime('%d %B %Y')}<br><br>
                    
                    <strong>Menu Type:</strong><br>
                    {datetime.now().strftime('%B')} Menus
                </div>
                
                <p>Best regards,<br>Holly Lea Menu System</p>
            </div>
            <div class="footer">
                This is an automated message from the Holly Lea Menu System
            </div>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(html_body, 'html'))
    
    # Attach menu file
    with open(os.getenv('MENU_FILE_PATH'), 'rb') as f:
        attachment = MIMEApplication(f.read(), _subtype=os.getenv('MENU_FILE_TYPE'))
        attachment.add_header('Content-Disposition', 'attachment', 
                            filename=f"Menu_{datetime.now().strftime('%Y%m%d')}.{os.getenv('MENU_FILE_TYPE')}")
        msg.attach(attachment)
    
    # Send email
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✉️  Email sent successfully at {datetime.now()}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False

def get_menu_settings():
    """Get latest menu settings from database"""
    settings_response = supabase.table('menu_settings')\
        .select('*')\
        .order('created_at', desc=True)\
        .limit(1)\
        .execute()
        
    return settings_response.data[0] if settings_response.data else None

def get_menu_template(season, menu_pair):
    """Get the correct menu template from Supabase"""
    response = supabase.table('menus')\
        .select('*')\
        .eq('name', f"{season}_{menu_pair}")\
        .execute()
        
    if not response.data:
        raise Exception(f"No menu template found for {season} {menu_pair}")
    
    return response.data[0]

def calculate_next_menu():
    """Calculate which menu should be sent next"""
    settings = get_menu_settings()
    today = datetime.now().date()
    
    # Calculate weeks since start
    start_date = datetime.strptime(settings['start_date'], '%Y-%m-%d').date()
    weeks_since_start = (today - start_date).days // 7
    
    # Calculate the next period start
    periods_elapsed = weeks_since_start // 2
    next_period_start = start_date + timedelta(days=periods_elapsed * 14)
    
    # If we're past this period, move to next one
    if today >= next_period_start:
        next_period_start += timedelta(days=14)
    
    # Calculate send date backwards from period start
    send_date = next_period_start - timedelta(days=settings['days_in_advance'])
    
    # Determine menu pair (1&2 or 3&4)
    is_odd_period = (periods_elapsed % 2) == 0
    menu_pair = "1_2" if is_odd_period else "3_4"
    
    # Check if we need to toggle season
    season = settings['season']
    if settings['season_change_date']:
        change_date = datetime.strptime(settings['season_change_date'], '%Y-%m-%d').date()
        if today >= change_date:
            season = 'winter' if season == 'summer' else 'summer'
            
            # Update settings with new season
            settings['season'] = season
            supabase.table('menu_settings').update(settings).eq('id', settings['id']).execute()
    
    return {
        'send_date': send_date,
        'period_start': next_period_start,
        'menu_pair': menu_pair,
        'season': season,
        'recipient_emails': settings['recipient_emails']
    }

def draw_dates_on_menu(image_data, start_date):
    """Draw dates on menu image"""
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(image_data))
        draw = ImageDraw.Draw(img)
        
        # Load a font (you'll need to provide a path to a .ttf font file)
        font = ImageFont.truetype("/path/to/your/font.ttf", 36)
        
        # Calculate dates for the two weeks
        week1_start = start_date
        week1_end = week1_start + timedelta(days=6)
        week2_start = week1_start + timedelta(days=7)
        week2_end = week2_start + timedelta(days=6)
        
        # Format date strings
        week1_text = f"{week1_start.strftime('%d %B')} - {week1_end.strftime('%d %B %Y')}"
        week2_text = f"{week2_start.strftime('%d %B')} - {week2_end.strftime('%d %B %Y')}"
        
        # Draw dates on image (you'll need to adjust coordinates)
        draw.text((100, 100), week1_text, font=font, fill='black')
        draw.text((100, 200), week2_text, font=font, fill='black')
        
        # Convert back to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format=img.format)
        return img_byte_arr.getvalue()
        
    except Exception as e:
        logger.log_activity(
            action="Draw Dates Failed",
            details=str(e),
            status="error"
        )
        return image_data  # Return original if processing fails

def send_menu_email(start_date, recipient_list, season):
    """Send menu email to recipients"""
    try:
        # Calculate menu pair based on start date
        weeks_since_start = (start_date - datetime.strptime(get_menu_settings()['start_date'], '%Y-%m-%d').date()).days // 7
        periods_elapsed = weeks_since_start // 2
        is_odd_period = (periods_elapsed % 2) == 0
        menu_pair = "1_2" if is_odd_period else "3_4"
        
        # Get menu templates
        menu_response = supabase.table('menus')\
            .select('*')\
            .eq('name', f"{season}_{menu_pair}")\
            .execute()
        
        if not menu_response.data:
            raise Exception(f"No menu template found for {season} {menu_pair}")
            
        # Format email content
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['Subject'] = f"Menu for period starting {start_date.strftime('%d %B %Y')}"
        
        # Use recipient list from settings
        if not recipient_list:
            raise Exception("No recipient emails configured")
            
        msg['To'] = ', '.join(recipient_list)
        
        body = f"""
        Hello,
        
        Please find attached the menu for the period starting {start_date.strftime('%A, %d %B %Y')}.
        
        Best regards,
        Menu System
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach menus
        for menu in menu_response.data:
            # Download menu from storage
            file_data = supabase.storage.from_('menus')\
                .download(menu['file_path'])
                
            # Draw dates on the menu
            processed_file_data = draw_dates_on_menu(file_data, start_date)
                
            attachment = MIMEApplication(processed_file_data)
            attachment.add_header(
                'Content-Disposition', 
                'attachment', 
                filename=os.path.basename(menu['file_path'])
            )
            msg.attach(attachment)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            
        logger.log_activity(
            action="Menu Email Sent",
            details=f"Sent menu for period starting {start_date}",
            status="success"
        )
        
        return True
        
    except Exception as e:
        logger.log_activity(
            action="Menu Email Failed",
            details=str(e),
            status="error"
        )
        print(f"❌ Email error: {str(e)}")
        return False

def check_and_send():
    """Main worker function"""
    try:
        next_menu = calculate_next_menu()
        today = datetime.now().date()
        
        # TEMPORARY TEST CODE - Remove after testing
        print("🧪 TEST MODE: Forcing menu send...")
        success = send_menu_email(next_menu['period_start'], next_menu['recipient_emails'], next_menu['season'])
        if success:
            print("✅ Test menu sent successfully!")
        else:
            print("❌ Test menu send failed!")
        return
        # END TEST CODE
        
        if today == next_menu['send_date']:
            logger.log_activity(
                action="Menu Send Started",
                details=f"Sending menu for period starting {next_menu['period_start']}"
            )
            success = send_menu_email(next_menu['period_start'], next_menu['recipient_emails'], next_menu['season'])
            
        else:
            logger.log_activity(
                action="Menu Check",
                details=f"No menu to send today. Next send date: {next_menu['send_date']}"
            )
            
    except Exception as e:
        logger.log_activity(
            action="Worker Error",
            details=str(e),
            status="error"
        )

def main():
    """Main service loop"""
    print("\n🚀 Worker service starting...")
    print(f"📁 Environment check:")
    print(f"- STATE_FILE: {os.getenv('STATE_FILE')}")
    print(f"- Working dir: {os.getcwd()}")
    print(f"📧 Using email: {SMTP_USERNAME}")
    print(f"👥 Sending to: {os.getenv('RECIPIENT_EMAILS')}")
    print(f"📁 State file path: {os.getenv('STATE_FILE', 'service_state.txt')}")
    
    while True:
        active = should_send_emails()
        print(f"\n⚡ Service status: {'ACTIVE' if active else 'PAUSED'}")
        
        if active:
            check_and_send()
        else:
            print(f"⏸️  Worker PID {os.getpid()} is paused, skipping email send")
        
        print(f"⏰ Next check in 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    logging.info("🚀 Menu worker starting...")
    main() 