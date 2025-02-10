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
        state_file = os.getenv('STATE_FILE', '/opt/render/service_state.txt')
        print(f"\n🔍 SUPER DEBUG at {datetime.now()}:")
        print(f"- Process ID: {os.getpid()}")
        print(f"- State file path: {state_file}")
        print(f"- File exists: {os.path.exists(state_file)}")
        
        # Create directory and file if they don't exist
        if not os.path.exists(state_file):
            print("📝 Creating state file...")
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            with open(state_file, 'w') as f:
                f.write('True')  # Default to active
            print("✅ State file created")
            
        with open(state_file, 'r') as f:
            content = f.read().strip()
            print(f"- Raw file content: '{content}'")
            print(f"- Content length: {len(content)}")
            print(f"- Content bytes: {[ord(c) for c in content]}")
            is_active = content.lower() == 'true'
            print(f"- Service should be: {'ACTIVE' if is_active else 'PAUSED'}")
            return is_active
            
    except Exception as e:
        print(f"❌ Error reading state file: {str(e)}")
        print(f"- Full error: {repr(e)}")
        return False  # Default to PAUSED on error

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