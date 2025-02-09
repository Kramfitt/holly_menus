import sys
import os
import schedule
import time
import yaml
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

print("=== MENU SCHEDULER STARTING ===", file=sys.stderr)

def load_config():
    # Load environment variables
    load_dotenv()
    
    # Load base config from yaml
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Override sensitive values with environment variables
    config['email']['smtp_server'] = os.getenv('SMTP_SERVER', config['email']['smtp_server'])
    config['email']['smtp_port'] = int(os.getenv('SMTP_PORT', config['email']['smtp_port']))
    config['email']['sender_email'] = os.getenv('SENDER_EMAIL', config['email']['sender_email'])
    config['recipients']['primary']['email'] = os.getenv('RECIPIENT_EMAIL', config['recipients']['primary']['email'])
    
    # Email password should ONLY come from environment variables
    config['email']['password'] = os.getenv('EMAIL_PASSWORD')
    
    print("Configuration loaded with environment variables", file=sys.stderr)
    return config

def determine_menu_details(current_date):
    """Calculate which menu should be sent based on the date"""
    config = load_config()
    
    # Calculate next menu start date (2 weeks from now)
    next_date = current_date + timedelta(days=14)
    
    # Determine season
    year = next_date.year
    summer_start = datetime.strptime(f"{year}-" + config['seasons']['summer']['start_date'][5:], "%Y-%m-%d")
    winter_start = datetime.strptime(f"{year}-" + config['seasons']['winter']['start_date'][5:], "%Y-%m-%d")
    
    is_summer = (summer_start <= next_date < winter_start)
    season = "Summer" if is_summer else "Winter"
    season_start = summer_start if is_summer else winter_start
    
    # Calculate week number (1-4)
    weeks_since_start = ((next_date - season_start).days // 14)
    week_number = (weeks_since_start % 4) + 1
    
    return {
        'start_date': next_date,
        'season': season,
        'week_number': week_number
    }

def get_menu_file_path(menu_details, config):
    """Get the path to the correct menu template file"""
    try:
        season = menu_details['season']
        week_number = menu_details['week_number']
        template_path = config['seasons'][season.lower()]['template_path']
        
        # Expected filename format: "Summer_Week_1.pdf" or "Winter_Week_1.pdf"
        filename = f"{season}_Week_{week_number}.pdf"
        full_path = os.path.join(template_path, filename)
        
        print(f"Looking for menu file: {full_path}", file=sys.stderr)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Menu file not found: {full_path}")
            
        return full_path
        
    except Exception as e:
        print(f"Error finding menu file: {str(e)}", file=sys.stderr)
        raise

def send_menu(menu_details, config):
    """Send the menu via email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{config['email']['sender_name']} <{config['email']['sender_email']}>"
        msg['To'] = config['recipients']['primary']['email']
        msg['Subject'] = f"Menu for week starting {menu_details['start_date'].strftime('%B %d, %Y')}"
        
        # Email body
        body = f"""Hello,

Please find attached the menu for the week starting {menu_details['start_date'].strftime('%B %d, %Y')}.
This is a {menu_details['season']} menu (Week {menu_details['week_number']}).

Best regards,
Menu System"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach menu file
        try:
            menu_path = get_menu_file_path(menu_details, config)
            with open(menu_path, 'rb') as f:
                pdf = MIMEApplication(f.read(), _subtype='pdf')
                pdf.add_header('Content-Disposition', 'attachment', 
                             filename=os.path.basename(menu_path))
                msg.attach(pdf)
                print(f"Menu file attached: {menu_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error attaching menu file: {str(e)}", file=sys.stderr)
            raise
        
        # Send email
        with smtplib.SMTP(config['email']['smtp_server'], config['email']['smtp_port']) as server:
            server.starttls()
            server.login(config['email']['sender_email'], config['email']['password'])
            server.send_message(msg)
            
        print(f"Menu email sent successfully for {menu_details['start_date'].strftime('%Y-%m-%d')}", file=sys.stderr)
        
    except Exception as e:
        print(f"Error sending menu email: {str(e)}", file=sys.stderr)
        raise

def send_test_email(config):
    """Send a test email to verify configuration"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{config['email']['sender_name']} <{config['email']['sender_email']}>"
        msg['To'] = config['email']['sender_email']  # Send to yourself for testing
        msg['Subject'] = "Menu Scheduler Test Email"
        
        body = """Hello,

This is a test email from the Menu Scheduler system.
If you're receiving this, the email configuration is working correctly.

Current configuration:
- SMTP Server: Working
- Authentication: Successful
- Email Sending: Operational

Best regards,
Menu System"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        print("Attempting to send test email...", file=sys.stderr)
        with smtplib.SMTP(config['email']['smtp_server'], config['email']['smtp_port']) as server:
            server.starttls()
            server.login(config['email']['sender_email'], config['email']['password'])
            server.send_message(msg)
            
        print("Test email sent successfully!", file=sys.stderr)
        
    except Exception as e:
        print(f"Error sending test email: {str(e)}", file=sys.stderr)
        raise

def check_and_send_menu():
    """Check if a menu needs to be sent today and send if needed"""
    try:
        config = load_config()
        current_date = datetime.now()
        
        # For testing: Send a test email every 5 minutes
        if current_date.minute % 5 == 0:
            print("Sending test email...", file=sys.stderr)
            send_test_email(config)
            return
            
        menu_details = determine_menu_details(current_date)
        days_until_start = (menu_details['start_date'] - current_date).days
        
        if days_until_start == config['schedule']['send_days_before']:
            print(f"Sending menu for {menu_details['season']} Week {menu_details['week_number']}", file=sys.stderr)
            send_menu(menu_details, config)
        else:
            print(f"No menu due today. Next menu starts in {days_until_start} days", file=sys.stderr)
            
    except Exception as e:
        print(f"Error in check_and_send_menu: {str(e)}", file=sys.stderr)

def validate_template_structure(config):
    """Validate that all required menu template files exist"""
    print("Validating template structure...", file=sys.stderr)
    missing_files = []
    current_date = datetime.now()
    
    # Determine current season
    year = current_date.year
    summer_start = datetime.strptime(f"{year}-" + config['seasons']['summer']['start_date'][5:], "%Y-%m-%d")
    winter_start = datetime.strptime(f"{year}-" + config['seasons']['winter']['start_date'][5:], "%Y-%m-%d")
    
    is_summer = (summer_start <= current_date < winter_start)
    current_season = "summer" if is_summer else "winter"
    
    print(f"Current season is: {current_season.capitalize()}", file=sys.stderr)
    
    # Only validate the current season's templates
    template_path = config['seasons'][current_season]['template_path']
    
    # Check if template directory exists
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template directory not found: {template_path}")
        
    # Check for all required week files
    for week in range(1, 5):
        filename = f"{current_season.capitalize()}_Week_{week}.pdf"
        full_path = os.path.join(template_path, filename)
        
        if not os.path.exists(full_path):
            missing_files.append(full_path)

    if missing_files:
        raise FileNotFoundError(
            f"Missing {current_season} template files:\n" + 
            "\n".join(f"- {f}" for f in missing_files)
        )
    
    print(f"{current_season.capitalize()} template structure validation successful!", file=sys.stderr)

try:
    # Load initial config
    print("Loading config...", file=sys.stderr)
    config = load_config()
    print("Config loaded successfully", file=sys.stderr)
    
    # Run check_and_send_menu every minute for testing
    # Later we'll change this to run at 9 AM
    schedule.every(1).minutes.do(check_and_send_menu)
    print("Schedule set up successfully", file=sys.stderr)
    
    print("Starting scheduler loop...", file=sys.stderr)
    while True:
        schedule.run_pending()
        time.sleep(60)

except Exception as e:
    print(f"Error in main loop: {str(e)}", file=sys.stderr)
    raise