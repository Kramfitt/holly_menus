import sys
import os
import schedule
import time
import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv

print("=== SCHEDULER TEST ===", file=sys.stderr)
print(f"Current directory: {os.getcwd()}", file=sys.stderr)

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

def test_job():
    try:
        config = load_config()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"Test job running at {current_time}", file=sys.stderr)
        print(f"Using email: {config['email']['sender_email']}", file=sys.stderr)
    except Exception as e:
        print(f"Error in test job: {str(e)}", file=sys.stderr)

try:
    # Load initial config
    print("Loading config...", file=sys.stderr)
    config = load_config()
    print("Config loaded successfully", file=sys.stderr)
    
    # Setup basic job
    print("Setting up test schedule...", file=sys.stderr)
    schedule.every(1).minutes.do(test_job)
    print("Schedule set up successfully", file=sys.stderr)
    
    print("Starting scheduler loop...", file=sys.stderr)
    while True:
        schedule.run_pending()
        time.sleep(60)

except Exception as e:
    print(f"Error in scheduler: {str(e)}", file=sys.stderr)
    raise