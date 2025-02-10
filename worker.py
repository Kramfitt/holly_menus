import os
from dotenv import load_dotenv
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import time
import redis

# Force load from .env file
load_dotenv(override=True)

# Near the top with other configs
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url)

# Set initial state if none exists
if redis_client.get('service_state') is None:
    print("📝 Setting initial Redis state to: false")
    redis_client.set('service_state', 'false')  # Start paused

def should_send_emails():
    """Check if email service is active"""
    try:
        state = redis_client.get('service_state')
        is_active = state == b'true' if state else False
        print(f"⚡ Service state: {'ACTIVE' if is_active else 'PAUSED'}")
        return is_active
    except Exception as e:
        print(f"❌ Redis error: {str(e)}")
        return False  # Default to paused on error

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