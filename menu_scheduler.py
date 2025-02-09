import sys
import os
import schedule
import time
import yaml
import logging
from datetime import datetime

print("=== SCHEDULER TEST ===", file=sys.stderr)
print(f"Current directory: {os.getcwd()}", file=sys.stderr)

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def test_job():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Test job running at {current_time}", file=sys.stderr)

try:
    # Load config
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