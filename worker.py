import sys
import os
import gc

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from datetime import datetime, timedelta
import time
import redis
from supabase import create_client
from app.utils.logger import get_logger
from config import Config, supabase, redis_client

# Create minimal Flask app for context
app = Flask(__name__)
config = Config()
app.config.from_object(config)

# Initialize Redis if not already initialized
if not redis_client:
    redis_host = config.REDIS_HOST
    redis_port = config.REDIS_PORT
    redis_url = config.REDIS_URL
    print(f"Connecting to Redis at {redis_url}")
    redis_client = redis.from_url(redis_url, decode_responses=True)

# Set initial state if none exists
if redis_client.get('service_state') is None:
    print("📝 Setting initial Redis state to: false")
    redis_client.set('service_state', 'false')  # Start paused

# Initialize logger
logger = get_logger()

def calculate_next_menu():
    """Calculate which menu should be sent next"""
    try:
        # Get current settings
        settings_response = supabase.table('menu_settings')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if not settings_response.data:
            logger.log_activity(
                action="Menu Calculation",
                details="No menu settings found",
                status="warning"
            )
            return None

        settings = settings_response.data[0]
        start_date = datetime.strptime(settings['start_date'], '%Y-%m-%d').date()
        today = datetime.now().date()

        # Calculate next menu period
        days_since_start = (today - start_date).days
        weeks_since_start = days_since_start // 7
        current_period = weeks_since_start // 2
        
        # Calculate next period start
        next_period_start = start_date + timedelta(weeks=current_period * 2)
        if today >= next_period_start:
            next_period_start += timedelta(weeks=2)

        # Calculate send date
        send_date = next_period_start - timedelta(days=settings['days_in_advance'])

        # Determine season and week
        season = settings['season']
        week_pair = "1_2" if (current_period % 2 == 0) else "3_4"

        return {
            'send_date': send_date,
            'period_start': next_period_start,
            'season': season,
            'menu_pair': week_pair
        }

    except Exception as e:
        logger.log_activity(
            action="Menu Calculation Failed",
            details=str(e),
            status="error"
        )
        return None

def send_menu_email(start_date, recipient_list, season, week_number=None):
    """Send menu email to recipients"""
    try:
        # Get template
        template = supabase.table('menu_templates')\
            .select('*')\
            .eq('season', season.lower())\
            .eq('week', week_number)\
            .execute()
            
        if not template.data:
            raise ValueError(f"No template found for {season} week {week_number}")
            
        template_url = template.data[0]['file_url']
        
        # Format dates
        period_end = start_date + timedelta(days=13)  # 2 weeks
        date_range = f"{start_date.strftime('%d %b')} - {period_end.strftime('%d %b %Y')}"
        
        # Send email (implement your email sending logic here)
        # For now, just log it
        logger.log_activity(
            action="Menu Email Sent",
            details={
                'recipients': recipient_list,
                'season': season,
                'week': week_number,
                'date_range': date_range,
                'template_url': template_url
            },
            status="success"
        )
        
        return True
        
    except Exception as e:
        logger.log_activity(
            action="Menu Email Failed",
            details=str(e),
            status="error"
        )
        return False

def run_worker():
    """Main worker loop"""
    with app.app_context():
        while True:
            try:
                # Check if service is active
                if redis_client.get('service_state') != b'true':
                    time.sleep(60)  # Check every minute
                    continue
                
                # Clean up memory before processing
                gc.collect()
                
                # Calculate next menu with memory management
                next_menu = None
                try:
                    next_menu = calculate_next_menu()
                except Exception as e:
                    print(f"Error calculating next menu: {e}")
                    time.sleep(300)  # Wait 5 minutes on error
                    continue
                
                if not next_menu:
                    time.sleep(300)  # Wait 5 minutes if no menu
                    continue
                
                # Check if it's time to send
                now = datetime.now().date()
                if now == next_menu['send_date']:
                    try:
                        # Get settings for recipients
                        settings = supabase.table('menu_settings')\
                            .select('*')\
                            .order('created_at', desc=True)\
                            .limit(1)\
                            .execute()
                        
                        if settings.data:
                            recipient_list = settings.data[0].get('recipient_emails', [])
                            if recipient_list:
                                # Process one recipient at a time
                                for recipient in recipient_list:
                                    try:
                                        send_menu_email(
                                            start_date=next_menu['period_start'],
                                            recipient_list=[recipient],  # Send to one recipient
                                            season=next_menu['season'],
                                            week_number=next_menu['menu_pair'].split('_')[0]
                                        )
                                        # Small delay between emails
                                        time.sleep(2)
                                    except Exception as e:
                                        print(f"Error sending to {recipient}: {e}")
                                        continue
                                    finally:
                                        # Clean up after each email
                                        gc.collect()
                    except Exception as e:
                        print(f"Error processing recipients: {e}")
                
                # Clean up and sleep
                gc.collect()
                time.sleep(3600)  # Check every hour
                
            except Exception as e:
                print(f"Worker error: {e}")
                time.sleep(300)  # Wait 5 minutes on error
            finally:
                # Final cleanup
                gc.collect()

if __name__ == '__main__':
    run_worker() 