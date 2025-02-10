import os
from dotenv import load_dotenv
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import time

# Force load from .env file
load_dotenv(override=True)

def read_state_file():
    """Read state file with retries"""
    state_file = '/opt/render/service_state.txt'
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if not os.path.exists(state_file):
                print(f"❌ State file missing (attempt {attempt + 1})")
                time.sleep(1)
                continue
                
            with open(state_file, 'r') as f:
                content = f.read().strip().lower()
                print(f"📄 Read state: '{content}' (attempt {attempt + 1})")
                return content == 'true'
                
        except Exception as e:
            print(f"❌ Error reading state: {str(e)} (attempt {attempt + 1})")
            time.sleep(1)
    
    print("❌ Failed to read state file after retries")
    return False  # Default to paused if can't read

def should_send_emails():
    """Check if email service is active"""
    is_active = read_state_file()
    print(f"\n🔍 Service state check at {datetime.now()}:")
    print(f"- Should send emails? {'YES' if is_active else 'NO'}")
    return is_active

def send_email():
    """Send email using settings from .env"""
    print(f"🔄 Worker PID {os.getpid()} attempting to send email")
    # Get settings
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT'))
    username = os.getenv('SMTP_USERNAME')
    password = os.getenv('SMTP_PASSWORD')
    recipients = os.getenv('RECIPIENT_EMAILS').split(',')
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = username
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = "Menu Service Test"
    
    body = "This is a test email from the menu service."
    msg.attach(MIMEText(body, 'plain'))

    # Send email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        print(f"✉️  Email sent successfully at {datetime.now()}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False

def main():
    """Main service loop"""
    print("\n🚀 Worker service starting...")
    print(f"📁 Environment check:")
    print(f"- STATE_FILE: {os.getenv('STATE_FILE')}")
    print(f"- Working dir: {os.getcwd()}")
    print(f"📧 Using email: {os.getenv('SMTP_USERNAME')}")
    print(f"👥 Sending to: {os.getenv('RECIPIENT_EMAILS')}")
    print(f"📁 State file path: {os.getenv('STATE_FILE', 'service_state.txt')}")
    
    while True:
        active = should_send_emails()
        print(f"\n⚡ Service status: {'ACTIVE' if active else 'PAUSED'}")
        
        if active:
            send_email()
        else:
            print(f"⏸️  Worker PID {os.getpid()} is paused, skipping email send")
        
        print(f"⏰ Next check in 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main() 