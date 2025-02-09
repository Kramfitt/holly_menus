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
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import tempfile

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

def add_dates_to_pdf(original_pdf_path, menu_details):
    """Add all week dates to the PDF"""
    try:
        # Create temporary files
        temp_dir = tempfile.mkdtemp()
        date_layer = os.path.join(temp_dir, "date.pdf")
        output_path = os.path.join(temp_dir, "menu_with_date.pdf")
        
        # Create the date layer
        c = canvas.Canvas(date_layer, pagesize=letter)
        c.setFont("Helvetica", 12)
        
        # Calculate all dates for the week
        start_date = menu_details['start_date']
        for day in range(7):
            current_date = start_date + timedelta(days=day)
            date_text = current_date.strftime('%a %d %b')  # e.g., "Mon 3 Feb"
            marker = f"{{{{DATE-{day+1}}}}}"
            
            # Find position of this marker and place date there
            # (We'll add marker detection code)
            
            # TODO: Need to implement marker detection to get x,y coordinates
            # For now, place dates in fixed positions
            x = 100  # Left margin
            y = 750 - (day * 20)  # Start from top, move down for each date
            c.drawString(x, y, date_text)
        
        c.save()
        
        # Merge original PDF with date layer
        original = PdfReader(original_pdf_path)
        date_layer_pdf = PdfReader(date_layer)
        
        writer = PdfWriter()
        page = original.pages[0]
        page.merge_page(date_layer_pdf.pages[0])
        writer.add_page(page)
        
        # Save the result
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        print(f"Date added successfully, temporary file: {output_path}", file=sys.stderr)
        return output_path
        
    except Exception as e:
        print(f"Error adding date to PDF: {str(e)}", file=sys.stderr)
        raise
    finally:
        # Cleanup will happen in the calling function
        pass

def send_menu(menu_details, config):
    """Send the menu via email"""
    temp_dir = None
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
        
        # Get and modify the menu file
        try:
            original_menu_path = get_menu_file_path(menu_details, config)
            dated_menu_path = add_dates_to_pdf(original_menu_path, menu_details)
            
            # Attach the modified PDF
            with open(dated_menu_path, 'rb') as f:
                pdf = MIMEApplication(f.read(), _subtype='pdf')
                pdf.add_header('Content-Disposition', 'attachment', 
                             filename=f"Menu_{menu_details['start_date'].strftime('%Y-%m-%d')}.pdf")
                msg.attach(pdf)
                print(f"Modified menu file attached", file=sys.stderr)
                
        except Exception as e:
            print(f"Error preparing menu file: {str(e)}", file=sys.stderr)
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
    finally:
        # Clean up temporary files
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)

def send_test_email(config):
    """Send a test email to verify configuration"""
    try:
        # Create test menu details
        test_menu_details = {
            'start_date': datetime.now() + timedelta(days=14),
            'season': 'Summer',
            'week_number': 1
        }
        
        msg = MIMEMultipart()
        msg['From'] = f"{config['email']['sender_name']} <{config['email']['sender_email']}>"
        msg['To'] = config['email']['sender_email']  # Send to yourself for testing
        msg['Subject'] = "Menu Scheduler Test - PDF Modification"
        
        body = """Hello,

This is a test email from the Menu Scheduler system.
Testing PDF modification and attachment.

Current configuration:
- SMTP Server: Working
- Authentication: Successful
- Email Sending: Operational
- PDF Modification: Testing

Best regards,
Menu System"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Test PDF modification
        try:
            original_menu_path = get_menu_file_path(test_menu_details, config)
            dated_menu_path = add_dates_to_pdf(original_menu_path, test_menu_details)
            
            # Attach the modified PDF
            with open(dated_menu_path, 'rb') as f:
                pdf = MIMEApplication(f.read(), _subtype='pdf')
                pdf.add_header('Content-Disposition', 'attachment', 
                             filename=f"Test_Menu_{test_menu_details['start_date'].strftime('%Y-%m-%d')}.pdf")
                msg.attach(pdf)
                print("Modified test menu file attached", file=sys.stderr)
                
        except Exception as e:
            print(f"Error preparing test menu file: {str(e)}", file=sys.stderr)
            raise
        
        print("Attempting to send test email with modified PDF...", file=sys.stderr)
        with smtplib.SMTP(config['email']['smtp_server'], config['email']['smtp_port']) as server:
            server.starttls()
            server.login(config['email']['sender_email'], config['email']['password'])
            server.send_message(msg)
            
        print("Test email with PDF sent successfully!", file=sys.stderr)
        
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
    print("\n=== SEASON CALCULATION DEBUG ===", file=sys.stderr)
    current_date = datetime.now()
    print(f"Current date: {current_date}", file=sys.stderr)
    
    # Determine current season
    year = current_date.year
    summer_start = datetime.strptime(f"{year}-" + config['seasons']['summer']['start_date'][5:], "%Y-%m-%d")
    winter_start = datetime.strptime(f"{year}-" + config['seasons']['winter']['start_date'][5:], "%Y-%m-%d")
    
    print(f"Summer starts: {summer_start}", file=sys.stderr)
    print(f"Winter starts: {winter_start}", file=sys.stderr)
    
    # Handle year wraparound for summer starting in December
    if current_date.month >= 12:
        summer_start = datetime.strptime(f"{year}-12-01", "%Y-%m-%d")
    else:
        summer_start = datetime.strptime(f"{year-1}-12-01", "%Y-%m-%d")
    
    is_summer = (summer_start <= current_date < winter_start)
    current_season = "summer" if is_summer else "winter"
    
    print(f"Adjusted summer start: {summer_start}", file=sys.stderr)
    print(f"Is summer? {is_summer}", file=sys.stderr)
    print(f"Current season: {current_season}", file=sys.stderr)
    print("=== END SEASON DEBUG ===\n", file=sys.stderr)
    
    # Rest of the validation code...

def list_server_files():
    """List all files in the application directory"""
    print("\n=== SERVER FILE STRUCTURE ===", file=sys.stderr)
    
    def print_directory_tree(startpath, prefix=''):
        """Print the directory tree structure"""
        for entry in os.listdir(startpath):
            path = os.path.join(startpath, entry)
            print(f"{prefix}├── {entry}", file=sys.stderr)
            if os.path.isdir(path):
                print_directory_tree(path, prefix + "│   ")
    
    try:
        print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
        print("\nDirectory contents:", file=sys.stderr)
        print_directory_tree('.')
        print("\n=== END FILE STRUCTURE ===\n", file=sys.stderr)
    except Exception as e:
        print(f"Error listing files: {str(e)}", file=sys.stderr)

# Add this to your startup code:
if __name__ == "__main__":
    try:
        print("=== STARTING MENU SCHEDULER ===", file=sys.stderr)
        
        # List all files on startup
        list_server_files()
        
        # Load initial config
        config = load_config()
        print("Config loaded successfully", file=sys.stderr)
        
        # Validate template structure
        validate_template_structure(config)
        
        # Setup schedule
        schedule.every(1).minutes.do(check_and_send_menu)
        print("Schedule set up successfully", file=sys.stderr)
        
        print("Starting scheduler loop...", file=sys.stderr)
        while True:
            schedule.run_pending()
            time.sleep(60)
            
    except Exception as e:
        print(f"Error in main loop: {str(e)}", file=sys.stderr)
        raise