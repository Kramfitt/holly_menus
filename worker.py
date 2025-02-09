import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables and add debug prints
print("Loading environment variables...")
load_dotenv()
print(f"SMTP_SERVER: {os.getenv('SMTP_SERVER')}")
print(f"SMTP_USERNAME: {os.getenv('SMTP_USERNAME')}")
print(f"SMTP_PASSWORD length: {len(os.getenv('SMTP_PASSWORD', ''))}")
print(f"RECIPIENT_EMAILS: {os.getenv('RECIPIENT_EMAILS')}")

def should_send_emails():
    try:
        with open(os.getenv('STATE_FILE', 'service_state.txt'), 'r') as f:
            return f.read().strip() == 'True'
    except:
        return True  # Default to active if file doesn't exist

def send_email():
    # Email settings from environment variables
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT'))
    username = 'ashvillenz@gmail.com' #os.getenv('SMTP_USERNAME')
    password = 'ktrf xmyb zcku jayt'#os.getenv('SMTP_PASSWORD')
    recipients = os.getenv('RECIPIENT_EMAILS').split(',')

    # Create message
    msg = MIMEMultipart()
    msg['From'] = username
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = "Menu Service Test"
    
    body = "This is a test email from the menu service."
    msg.attach(MIMEText(body, 'plain'))

    # Send email - using same code as test_smtp.py
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        
        # Debug print
        print(f"Attempting login with username: {username}")
        print(f"Password length: {len(password)}")
        
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        print(f"Email sent successfully at {datetime.now()}")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

def main():
    print("Worker service starting...")
    while True:
        if should_send_emails():
            send_email()
        else:
            print("Service is paused, skipping email send")
        
        # Wait for 60 seconds before next check
        time.sleep(60)

if __name__ == "__main__":
    main() 