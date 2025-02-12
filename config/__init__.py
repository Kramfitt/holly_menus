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

# Remove any proxy settings if they exist
if hasattr(supabase, '_http_client'):
    if hasattr(supabase._http_client, 'proxies'):
        delattr(supabase._http_client, 'proxies')

# Initialize Redis client
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url)

# Email settings
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT')) if os.getenv('SMTP_PORT') else None
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Security settings
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY must be set in environment")

DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD')
if not DASHBOARD_PASSWORD:
    raise ValueError("DASHBOARD_PASSWORD must be set in environment")

# Print configuration status (remove in production)
print("\nConfiguration Status:")
print(f"- SUPABASE_URL: {'Set' if os.getenv('SUPABASE_URL') else 'Missing'}")
print(f"- SUPABASE_KEY: {'Set' if os.getenv('SUPABASE_KEY') else 'Missing'}")
print(f"- REDIS_URL: {'Set' if os.getenv('REDIS_URL') else 'Using default'}")
print(f"- SECRET_KEY: {'Set' if SECRET_KEY else 'Missing'}")
print(f"- DASHBOARD_PASSWORD: {'Set' if DASHBOARD_PASSWORD else 'Missing'}")
