import schedule
import time
from datetime import datetime, timedelta
import logging
import yaml
from menu_autosender import load_config, calculate_next_menu_date, process_menu

def should_send_menu(config):
    """
    Determine if we should send a menu today
    """
    current_date = datetime.now()
    next_schedule = calculate_next_menu_date(current_date)
    
    days_until_start = (next_schedule.start_date - current_date).days
    should_send = days_until_start == config['schedule']['send_days_before']
    
    if should_send:
        logging.info(f"Menu due for sending: {next_schedule.menu_type} Week {next_schedule.week_number}")
    
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
        # Load config and setup logging
        config = load_config()
        
        # Ensure logs directory exists
        import os
        os.makedirs(config['paths']['logs'], exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            filename=f"{config['paths']['logs']}/scheduler.log",
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Add console logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(console_handler)
        
        logging.info("Starting menu scheduler service")
        
        # Start the scheduler
        run_scheduler()
        
    except Exception as e:
        logging.error(f"Fatal error in scheduler: {str(e)}")
        raise