import schedule
import time
from datetime import datetime, timedelta
import logging
import yaml
from menu_autosender import load_config, calculate_next_menu_date, process_menu
import os
import sys

# Add immediate print for debugging
print("Script starting...", file=sys.stderr)

def should_send_menu(config):
    """
    Determine if we should send a menu today
    """
    print("Checking if menu should be sent...", file=sys.stderr)
    current_date = datetime.now()
    next_schedule = calculate_next_menu_date(current_date)
    
    days_until_start = (next_schedule.start_date - current_date).days
    should_send = days_until_start == config['schedule']['send_days_before']
    
    if should_send:
        print(f"Menu due for sending: {next_schedule.menu_type} Week {next_schedule.week_number}", file=sys.stderr)
    
    return should_send, next_schedule

def check_and_send_menu():
    """
    Main function that runs on schedule
    """
    try:
        config = load_config()
        should_send, next_schedule = should_send_menu(config)
        
        if should_send:
            process_menu(next_schedule, config)
            logging.info("Scheduled menu sent successfully")
        else:
            logging.debug("No menu due for sending today")
            
    except Exception as e:
        logging.error(f"Error in scheduled execution: {str(e)}")

def run_scheduler():
    """
    Set up and run the scheduler
    """
    config = load_config()
    send_time = config['schedule']['send_time']
    
    logging.info(f"Starting scheduler - will check daily at {send_time}")
    
    # Schedule daily check
    schedule.every().day.at(send_time).do(check_and_send_menu)
    
    # Run immediate check when starting
    check_and_send_menu()
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except Exception as e:
            logging.error(f"Error in scheduler loop: {str(e)}")
            time.sleep(300)  # Wait 5 minutes before retrying if there's an error

if __name__ == "__main__":
    try:
        # Basic print statements that should show up immediately
        print("=== STARTING MENU SCHEDULER ===", file=sys.stderr)
        print(f"Python version: {sys.version}", file=sys.stderr)
        print(f"Current directory: {os.getcwd()}", file=sys.stderr)
        print("Attempting to list directory contents:", file=sys.stderr)
        print(os.listdir('.'), file=sys.stderr)
        
        # Try loading config
        print("Attempting to load config...", file=sys.stderr)
        config = load_config()
        print("Config loaded successfully", file=sys.stderr)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            stream=sys.stderr  # Ensure logging goes to stderr
        )
        
        logging.info("=== Menu Scheduler Starting Up ===")
        logging.info(f"Current working directory: {os.getcwd()}")
        logging.info("Service initialized and running...")
        
        # Start the scheduler
        run_scheduler()
        
    except Exception as e:
        print(f"Fatal error in scheduler: {str(e)}", file=sys.stderr)
        raise