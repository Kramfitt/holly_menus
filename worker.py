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

def should_send_emails():
    """Check if email service is active"""
    try:
        state_file = os.getenv('STATE_FILE', 'service_state.txt')
        print(f"\n📁 Worker PID {os.getpid()} checking state file: {state_file}")
        
        with open(state_file, 'r') as f:
            content = f.read().strip()
            is_active = content == 'True'
            print(f"📄 State file content: '{content}'")
            print(f"🔍 Service active? {is_active}")
            return is_active
    except FileNotFoundError:
        print(f"❌ State file not found: {state_file}")
        return True
    except Exception as e:
        print(f"❌ Error reading state file: {str(e)}")
        return True

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
    print(f"\n🚀 Worker service starting... PID: {os.getpid()}")
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