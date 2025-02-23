from datetime import datetime, timedelta
import calendar
from dataclasses import dataclass
import schedule
import time
import yaml
import logging 
import sys

@dataclass
class MenuSchedule:
    start_date: datetime
    menu_type: str  # "Summer" or "Winter"
    week_number: int  # 1-4
    recipient_email: str

def calculate_next_menu_date(current_date):
    """
    Calculate the next menu start date and determine which menu to use.
    Returns MenuSchedule object.
    """
    config = load_config()
    
    # Calculate next menu date (2 weeks from current)
    next_date = current_date + timedelta(days=14)
    
    # Get current settings
    settings = get_menu_settings()
    if not settings:
        print("No settings found, using default season calculation", file=sys.stderr)
        # Fall back to config-based season calculation
        year = next_date.year
        summer_start = datetime.strptime(f"{year}-" + config['seasons']['summer']['start_date'][5:], "%Y-%m-%d")
        winter_start = datetime.strptime(f"{year}-" + config['seasons']['winter']['start_date'][5:], "%Y-%m-%d")
        
        # Adjust for year boundary if needed
        if next_date < summer_start and next_date.month >= 1:
            summer_start = datetime.strptime(f"{year-1}-" + config['seasons']['summer']['start_date'][5:], "%Y-%m-%d")
            winter_start = datetime.strptime(f"{year-1}-" + config['seasons']['winter']['start_date'][5:], "%Y-%m-%d")
        
        # Determine season
        is_summer = (summer_start <= next_date < winter_start)
        season = "Summer" if is_summer else "Winter"
        
        # Calculate week number (1-4)
        season_start = summer_start if is_summer else winter_start
        weeks_since_start = ((next_date - season_start).days // 14)
        week_number = (weeks_since_start % 4) + 1
    else:
        print("Using settings-based season calculation", file=sys.stderr)
        # Use settings-based season calculation
        season = settings['season'].capitalize()
        if settings.get('season_change_date'):
            change_date = datetime.strptime(settings['season_change_date'], '%Y-%m-%d').date()
            if next_date.date() >= change_date:
                season = 'Winter' if season == 'Summer' else 'Summer'
        
        # Calculate week number (1-4) from start date
        start_date = datetime.strptime(settings['start_date'], '%Y-%m-%d').date()
        weeks_since_start = ((next_date.date() - start_date).days // 14)
        week_number = (weeks_since_start % 4) + 1
        
        print(f"Settings season: {settings['season']}", file=sys.stderr)
        print(f"Change date: {settings.get('season_change_date')}", file=sys.stderr)
        print(f"Week number: {week_number}", file=sys.stderr)
    
    return MenuSchedule(
        start_date=next_date,
        menu_type=season,
        week_number=week_number,
        recipient_email=config['recipients']['primary']['email']
    )

def generate_menu(schedule):
    """
    Generate the menu based on the schedule.
    """
    template_path = f"templates/{schedule.menu_type}_Week_{schedule.week_number}.pdf"
    output_path = f"menus/Menu_{schedule.start_date.strftime('%Y%m%d')}.pdf"
    
    # Your existing menu generation code here
    # But instead of copying headers, update date fields
    
    return output_path

def send_menu(file_path, schedule):
    """
    Send the menu via email.
    """
    subject = f"Menu for period starting {schedule.start_date.strftime('%B %d, %Y')}"
    body = f"""
    Please find attached the menu for the period:
    {schedule.start_date.strftime('%B %d, %Y')} - {(schedule.start_date + timedelta(days=13)).strftime('%B %d, %Y')}
    
    Menu Type: {schedule.menu_type} Week {schedule.week_number}
    """
    
    # Email sending code using smtplib or a service like SendGrid
    logging.info(f"Menu sent successfully to {schedule.recipient_email}")

def load_config():
    with open('config.yaml', 'r') as file:
        return yaml.safe_load(file)

def check_and_send_menus():
    config = load_config()
    today = datetime.now()
    
    # Check if we need to send a menu today
    next_schedule = calculate_next_menu_date(today)
    days_until_start = (next_schedule.start_date - today).days
    
    if days_until_start == config['schedule']['send_days_before']:
        menu_path = generate_menu(next_schedule)
        send_menu(menu_path, next_schedule)

# Run check daily at 9 AM
schedule.every().day.at("09:00").do(check_and_send_menus)

while True:
    schedule.run_pending()
    time.sleep(60)  

logging.basicConfig(
    filename='menu_scheduler.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def safe_menu_generation():
    try:
        check_and_send_menus()
        logging.info("Menu generation completed successfully")
    except Exception as e:
        logging.error(f"Error generating menu: {str(e)}")
        # Could add notification here for errors    

def main():
    # Get today's date
    today = datetime.now()
    
    # Calculate next menu schedule
    next_schedule = calculate_next_menu_date(today)
    
    print(f"""
    Next Menu Details:
    Start Date: {next_schedule.start_date.strftime('%B %d, %Y')}
    Type: {next_schedule.menu_type} Week {next_schedule.week_number}
    Recipient: {next_schedule.recipient_email}
    """)
    
    # Generate and send menu
    menu_path = generate_menu(next_schedule)
    send_menu(menu_path, next_schedule)

if __name__ == "__main__":
    main()