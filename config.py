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

# Mock Redis for development
class MockRedis:
    def __init__(self):
        self._data = {}
        print("🔧 Using Mock Redis for development")
    
    def get(self, key):
        return self._data.get(key, b'false')
    
    def set(self, key, value):
        self._data[key] = value.encode() if isinstance(value, str) else value
        return True
    
    def from_url(self, *args, **kwargs):
        return self

# Initialize Redis client with fallback
if os.getenv('FLASK_ENV') == 'development':
    redis_client = MockRedis()
else:
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        redis_client = redis.from_url(redis_url)
        print("✅ Redis connected")
    except redis.ConnectionError:
        print("⚠️ Redis not available, using mock")
        redis_client = MockRedis()

# Email settings
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT')) if os.getenv('SMTP_PORT') else None
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# App settings
SECRET_KEY = os.getenv('SECRET_KEY', 'dev')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD')

# Add this to config.py
REQUIRED_CONFIG = [
    'SECRET_KEY',
    'DASHBOARD_PASSWORD',
    'SMTP_SERVER',
    'SMTP_PORT',
    'SMTP_USERNAME',
    'SMTP_PASSWORD'
] 