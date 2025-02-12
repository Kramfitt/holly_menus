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

# Add near the top with other exports
REQUIRED_CONFIG = [
    'SECRET_KEY',
    'DASHBOARD_PASSWORD',
    'SMTP_SERVER',
    'SMTP_PORT',
    'SMTP_USERNAME',
    'SMTP_PASSWORD'
]

# Export in __all__
__all__ = [
    'supabase',
    'redis_client',
    'SMTP_SERVER',
    'SMTP_PORT',
    'SMTP_USERNAME',
    'SMTP_PASSWORD',
    'SECRET_KEY',
    'DASHBOARD_PASSWORD',
    'REQUIRED_CONFIG'  # Add this
]

def validate_config():
    """Validate all required configuration"""
    errors = []
    
    # Check required values
    for key in REQUIRED_CONFIG:
        value = os.getenv(key)
        if not value:
            errors.append(f"Missing {key}")
            continue
            
        # Additional validation for specific fields
        if key == 'SMTP_PORT':
            try:
                port = int(value)
                if port < 1 or port > 65535:
                    errors.append(f"Invalid SMTP_PORT: must be between 1 and 65535")
            except ValueError:
                errors.append(f"Invalid SMTP_PORT: must be a number")
                
        elif key == 'SMTP_SERVER':
            if not value.strip():
                errors.append("SMTP_SERVER cannot be empty")
                
        elif key in ['SECRET_KEY', 'DASHBOARD_PASSWORD']:
            if len(value) < 8:
                errors.append(f"{key} must be at least 8 characters")
    
    # Check database configuration
    if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_KEY'):
        errors.append("Missing Supabase configuration")
    
    # Check Redis configuration
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    if not redis_url.startswith(('redis://', 'rediss://')):
        errors.append("Invalid REDIS_URL format")
    
    if errors:
        raise ValueError("\n".join(errors))

# Move initialization after validation
try:
    validate_config()
    
    # Initialize clients only after validation
    supabase = create_client(
        supabase_url=os.getenv('SUPABASE_URL'),
        supabase_key=os.getenv('SUPABASE_KEY')
    )
    
    redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
    
except Exception as e:
    print(f"Configuration Error: {str(e)}")
    raise
