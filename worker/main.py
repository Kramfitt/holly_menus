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
from app.utils.logger import ActivityLogger
from app.utils.notifications import NotificationManager
from config import supabase, redis_client, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
from PIL import Image, ImageDraw, ImageFont
import io
from email.mime.image import MIMEImage
from app.services.menu_service import MenuService
from app.services.email_service import EmailService
from app.utils.logger import Logger
from worker.scheduler import MenuScheduler
import requests

# Force load from .env file
load_dotenv(override=True)

# Near the top with other configs
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_url = f"redis://{redis_host}:{redis_port}"
print(f"Connecting to Redis at {redis_url}")
redis_client = redis.from_url(redis_url, decode_responses=True)

# Set initial state if none exists
if redis_client.get('service_state') is None:
    print("📝 Setting initial Redis state to: false")
    redis_client.set('service_state', 'false')  # Start paused

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

def get_menu_template(season, week_number):
    """Get menu template from storage"""
    try:
        template = supabase.table('menu_templates')\
            .select('*')\
            .eq('season', season.lower())\
            .eq('week', int(week_number) if season.lower() != 'dates' else 0)\
            .execute()
            
        if not template.data:
            return None
            
        return template.data[0]
        
    except Exception as e:
        print(f"Error getting template: {e}")
        return None

def calculate_next_menu():
    """Calculate which menu should be sent next"""
    try:
        settings = get_menu_settings()
        if not settings:
            logger.log_activity(
                action="Menu Calculation",
                details="No menu settings found",
                status="warning"
            )
            return None
            
        today = datetime.now().date()
        
        # Calculate weeks since start
        start_date = datetime.strptime(settings['start_date'], '%Y-%m-%d').date()
        weeks_since_start = (today - start_date).days // 7
        current_week = (weeks_since_start % 4) + 1
        
        # Calculate the next period start
        periods_elapsed = weeks_since_start // 2
        next_period_start = start_date + timedelta(days=periods_elapsed * 14)
        
        # If we're past this period, move to next one
        if today >= next_period_start:
            next_period_start += timedelta(days=14)
        
        # Calculate send date backwards from period start
        send_date = next_period_start - timedelta(days=settings['days_in_advance'])
        
        # Determine season
        season = settings['season']
        if settings['season_change_date']:
            change_date = datetime.strptime(settings['season_change_date'], '%Y-%m-%d').date()
            if today >= change_date:
                season = 'winter' if season == 'summer' else 'summer'
        
        # Verify menu template exists before returning
        if not check_menu_template_exists(season, current_week):
            logger.log_activity(
                action="Menu Check",
                details=f"Menu template missing for {season.lower()} week {current_week}",
                status="warning"
            )
            return {
                'send_date': send_date,  # Include send_date even if template missing
                'period_start': next_period_start,
                'season': season,
                'week': current_week,
                'template_missing': True,
                'recipient_emails': settings['recipient_emails']
            }
            
        return {
            'send_date': send_date,
            'period_start': next_period_start,
            'season': season,
            'week': current_week,
            'template_missing': False,
            'recipient_emails': settings['recipient_emails']
        }
        
    except Exception as e:
        logger.log_activity(
            action="Menu Calculation Failed",
            details=str(e),
            status="error"
        )
        return None

def check_menu_template_exists(season, week_number):
    """Check if a menu template exists before trying to send it"""
    try:
        menu_name = f"{season.lower()}_week_{week_number}"
        print(f"Checking for menu template: {menu_name}")  # Debug log
        response = supabase.table('menus')\
            .select('*')\
            .eq('name', menu_name)\
            .execute()
        exists = bool(response.data)
        print(f"Template exists: {exists}")  # Debug log
        return exists
    except Exception as e:
        print(f"Error checking template: {str(e)}")  # Debug log
        return False

def draw_dates_on_menu(image_data, start_date):
    """Draw dates on menu image"""
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(image_data))
        draw = ImageDraw.Draw(img)
        
        # System font paths based on common locations
        font = None
        font_paths = [
            # Linux system fonts
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            # macOS system fonts
            '/System/Library/Fonts/Helvetica.ttc',
            # Windows system fonts
            'C:/Windows/Fonts/arial.ttf'
        ]
        
        # Try to find a system font
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 36)
                    break
            except Exception:
                continue
        
        # If no system font found, use default
        if not font:
            print("No system fonts found, using default font")
            font = ImageFont.load_default()
        
        # Calculate dates for the week
        week_end = start_date + timedelta(days=6)
        
        # Format date string
        date_text = f"{start_date.strftime('%d %B')} - {week_end.strftime('%d %B %Y')}"
        
        # Calculate text size for positioning
        text_bbox = draw.textbbox((0, 0), date_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        
        # Position text in top right corner with padding
        x = img.width - text_width - 50  # 50px padding from right
        y = 50  # 50px from top
        
        # Draw white background for better readability
        padding = 10
        draw.rectangle([x-padding, y-padding, x+text_width+padding, y+text_bbox[3]+padding], 
                      fill='white', outline='black')
        
        # Draw text
        draw.text((x, y), date_text, font=font, fill='black')
        
        # Convert back to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format=img.format if img.format else 'PNG')
        return img_byte_arr.getvalue()
        
    except Exception as e:
        logger.log_activity(
            action="Draw Dates Failed",
            details=str(e),
            status="error"
        )
        return image_data  # Return original if processing fails

def send_menu_email(start_date, recipient_list, season, week_number):
    """Send menu email to recipients"""
    try:
        # Get menu template
        menu_template = get_menu_template(season, week_number)
        if not menu_template:
            raise ValueError(f"No template found for {season} week {week_number}")

        # Get dates template
        dates_template = get_menu_template('dates', 0)  # Use week=0 for dates template
        if not dates_template:
            raise ValueError("Dates header template not found")
        
        dates_template_url = dates_template.get('template_url')
        if not dates_template_url:
            raise ValueError("Invalid dates template URL")

        # Create MenuService instance
        menu_service = MenuService(db=supabase, storage=supabase.storage)

        # Merge the templates
        merged_template = menu_service.merge_header_with_template(
            source_image=dates_template_url,
            template_path=menu_template['template_url'],
            header_proportion=0.20  # Header takes up 20% of the height
        )

        if not merged_template:
            raise ValueError("Failed to merge templates")

        # Format dates
        period_start = start_date
        period_end = period_start + timedelta(days=13)  # 2 weeks
        date_range = f"{period_start.strftime('%d %b')} - {period_end.strftime('%d %b %Y')}"

        # Create email message
        msg = MIMEMultipart()
        msg['From'] = os.getenv('SMTP_USERNAME')
        msg['To'] = ', '.join(recipient_list)
        msg['Subject'] = f"Menu for week starting {period_start.strftime('%B %d, %Y')}"

        # Email body
        body = f"""Hello,

Please find attached the menu for the period:
{date_range}

Menu Type: {season} Week {week_number}

Best regards,
Menu System"""

        msg.attach(MIMEText(body, 'plain'))

        # Download and attach the merged template
        response = requests.get(merged_template)
        if response.status_code == 200:
            attachment = MIMEApplication(response.content, _subtype='png')
            attachment.add_header('Content-Disposition', 'attachment', 
                                filename=f"Menu_{period_start.strftime('%Y-%m-%d')}.png")
            msg.attach(attachment)
        else:
            raise ValueError("Failed to download merged template")

        # Send email
        with smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
            server.send_message(msg)

        get_logger().log_activity(
            action="Menu Email Sent",
            details={
                'recipients': recipient_list,
                'season': season,
                'week': week_number,
                'date_range': date_range
            },
            status="success"
        )

        return True

    except Exception as e:
        get_logger().log_activity(
            action="Menu Email Failed",
            details=str(e),
            status="error"
        )
        return False

def check_and_send():
    """Main worker function"""
    try:
        next_menu = calculate_next_menu()
        if not next_menu:
            logger.log_activity(
                action="Menu Check",
                details="Could not calculate next menu",
                status="warning"
            )
            return
            
        today = datetime.now().date()
        
        # Skip if template is missing unless in debug mode
        if next_menu.get('template_missing') and redis_client.get('debug_mode') != b'true':
            logger.log_activity(
                action="Menu Check",
                details=f"Menu template missing for {next_menu['season']} week {next_menu['week']}",
                status="warning"
            )
            return
            
        # TEMPORARY TEST CODE - Remove after testing
        if redis_client.get('debug_mode') == b'true':
            print("🧪 TEST MODE: Forcing menu send...")
            success = send_menu_email(
                next_menu['period_start'], 
                next_menu['recipient_emails'], 
                next_menu['season'], 
                next_menu['week']
            )
            if success:
                print("✅ Test menu sent successfully!")
            else:
                print("❌ Test menu send failed!")
            return
            
        if today == next_menu['send_date']:
            logger.log_activity(
                action="Menu Send Started",
                details=f"Sending menu for period starting {next_menu['period_start']}"
            )
            success = send_menu_email(
                next_menu['period_start'], 
                next_menu['recipient_emails'], 
                next_menu['season'],
                next_menu['week']
            )
            
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
    print("Worker starting...")
    # Initialize services
    logger = Logger()
    menu_service = MenuService(db=supabase, storage=supabase.storage)
    email_service = EmailService(config={
        'SMTP_SERVER': SMTP_SERVER,
        'SMTP_PORT': SMTP_PORT,
        'SMTP_USERNAME': SMTP_USERNAME,
        'SMTP_PASSWORD': SMTP_PASSWORD
    })
    
    # Initialize and run scheduler
    scheduler = MenuScheduler(menu_service, email_service, logger)
    scheduler.run()

def test_menu_processing():
    """Test function to verify menu processing"""
    try:
        # Get a test menu
        season = "winter"  # or "summer"
        week = 1  # 1-4
        start_date = datetime.now().date()
        
        print(f"Testing menu processing for {season} week {week}")
        
        # Get templates
        template = get_menu_template(season, week)
        if not template:
            raise ValueError(f"No template found for {season} week {week}")
            
        dates_template = get_menu_template('dates', 0)
        if not dates_template:
            raise ValueError("Dates header template not found")
        
        # Test template merging
        menu_service = MenuService(db=supabase, storage=supabase.storage)
        merged_template = menu_service.merge_header_with_template(
            source_image=dates_template['template_url'],
            template_path=template['template_url'],
            header_proportion=0.20
        )
        
        if not merged_template:
            raise ValueError("Failed to merge templates")
            
        print(f"Template merging successful: {merged_template}")
        
        # Download and save test output
        response = requests.get(merged_template)
        if response.status_code == 200:
            with open('test_menu.png', 'wb') as f:
                f.write(response.content)
            print("Test file saved as test_menu.png")
        else:
            raise ValueError("Failed to download merged template")
        
        return True
    except Exception as e:
        print(f"Test failed: {str(e)}")
        return False

def log_activity(action, details, status):
    # Sanitize any sensitive data before logging
    if 'email' in details:
        details = details.replace(details.split('@')[0], '***')

if __name__ == "__main__":
    logging.info("🚀 Menu worker starting...")
    main()
    test_menu_processing() 