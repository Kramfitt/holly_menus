import os
from dotenv import load_dotenv
import redis
from supabase import create_client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase = create_client(
    supabase_url=os.getenv('SUPABASE_URL'),
    supabase_key=os.getenv('SUPABASE_KEY')
)

# Initialize Redis client
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url)

# Email settings
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT')) if os.getenv('SMTP_PORT') else None
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# App settings
SECRET_KEY = os.getenv('SECRET_KEY', 'dev')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD') 