import os
import re
from dotenv import load_dotenv
import redis
from supabase import create_client, Client
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json
from datetime import datetime

# Move to top with other constants
REQUIRED_CONFIG = {
    'SECRET_KEY': True,
    'DASHBOARD_PASSWORD': True,
    'SMTP_SERVER': True,
    'SMTP_PORT': True,
    'SMTP_USERNAME': True,
    'SMTP_PASSWORD': True,
    'SUPABASE_URL': True,
    'SUPABASE_KEY': True
}

# Other constants
MIN_PASSWORD_LENGTH = 1  # Super permissive for development
VALID_EMAIL_REGEX = r'.+@.+'  # Basic email validation

@dataclass
class ConfigError:
    """Configuration error details"""
    key: str
    value: Any
    message: str
    severity: str = 'error'  # error, warning, info
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            'key': self.key,
            'value': '***' if 'password' in self.key.lower() else self.value,
            'message': self.message,
            'severity': self.severity
        }

def validate_email(email: str) -> bool:
    """Validate email format"""
    return bool(re.match(VALID_EMAIL_REGEX, email))

def validate_port(port: int) -> bool:
    """Validate port number"""
    return 1 <= port <= 65535

def validate_url(url: str) -> bool:
    """Validate URL format"""
    return url.startswith(('http://', 'https://'))

def format_error_report(errors: List[ConfigError], warnings: List[ConfigError]) -> str:
    """Format configuration errors and warnings into readable report"""
    report = []
    
    if errors:
        report.append("\n🚫 Configuration Errors:")
        for error in errors:
            report.append(f"  • {error.key}: {error.message}")
            if error.value and not any(s in error.key.lower() for s in ['password', 'key', 'secret']):
                report.append(f"    Current value: {error.value}")
    
    if warnings:
        report.append("\n⚠️ Configuration Warnings:")
        for warning in warnings:
            report.append(f"  • {warning.key}: {warning.message}")
    
    if not errors and not warnings:
        report.append("\n✅ Configuration validated successfully")
    
    return "\n".join(report)

def log_config_status(errors: List[ConfigError], warnings: List[ConfigError]) -> None:
    """Log configuration status in JSON format"""
    status = {
        'timestamp': datetime.now().isoformat(),
        'status': 'error' if errors else 'warning' if warnings else 'ok',
        'errors': [e.to_dict() for e in errors],
        'warnings': [w.to_dict() for w in warnings]
    }
    
    # Log to file
    try:
        os.makedirs('logs', exist_ok=True)
        with open('logs/config_status.json', 'w') as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        print(f"Failed to write config status: {e}")
    
    # Print human-readable report
    print(format_error_report(errors, warnings))

def validate_config() -> None:
    """Validate all required configuration with detailed error reporting"""
    errors: List[ConfigError] = []
    warnings: List[ConfigError] = []
    
    try:
        # First check if values exist
        missing = []
        for key in REQUIRED_CONFIG:
            value = os.getenv(key)
            if not value:
                errors.append(ConfigError(
                    key=key,
                    value=None,
                    message=f"Missing required configuration",
                    severity='error'
                ))
        
        if missing:
            # Fail fast on missing required config
            error_msgs = [f"{e.key}: {e.message}" for e in errors]
            raise ValueError("\n".join(error_msgs))
        
        # Validate SMTP settings
        try:
            port = int(os.getenv('SMTP_PORT', '0'))
            if not validate_port(port):
                errors.append(ConfigError(
                    key='SMTP_PORT',
                    value=port,
                    message=f"Must be between 1 and 65535"
                ))
        except ValueError:
            errors.append(ConfigError(
                key='SMTP_PORT',
                value=os.getenv('SMTP_PORT'),
                message="Must be a valid number"
            ))
        
        smtp_server = os.getenv('SMTP_SERVER', '').strip()
        if not smtp_server:
            errors.append(ConfigError(
                key='SMTP_SERVER',
                value=smtp_server,
                message="Cannot be empty"
            ))
            
        smtp_username = os.getenv('SMTP_USERNAME', '')
        if not validate_email(smtp_username):
            errors.append(ConfigError(
                key='SMTP_USERNAME',
                value=smtp_username,
                message="Must be a valid email address"
            ))
            
        # Security validation with strength checks
        secret_key = os.getenv('SECRET_KEY', '')
        if len(secret_key) < MIN_PASSWORD_LENGTH:
            errors.append(ConfigError(
                key='SECRET_KEY',
                value='*' * len(secret_key),  # Don't log actual value
                message=f"Must be at least {MIN_PASSWORD_LENGTH} characters"
            ))
        elif len(secret_key) < 16:  # Change from error to warning
            warnings.append(ConfigError(
                key='SECRET_KEY',
                value='*' * len(secret_key),
                message="Recommended to use at least 16 characters in production",
                severity='warning'
            ))
            
        dashboard_pwd = os.getenv('DASHBOARD_PASSWORD', '')
        if len(dashboard_pwd) < 8:  # Still warn but don't error
            warnings.append(ConfigError(
                key='DASHBOARD_PASSWORD',
                value='*' * len(dashboard_pwd),
                message="Recommended to use at least 8 characters in production",
                severity='warning'
            ))
            
        # Database validation
        supabase_url = os.getenv('SUPABASE_URL', '')
        if not validate_url(supabase_url):
            errors.append(ConfigError(
                key='SUPABASE_URL',
                value=supabase_url,
                message="Must be a valid HTTPS URL"
            ))
            
        supabase_key = os.getenv('SUPABASE_KEY', '')
        if len(supabase_key) < 20:
            errors.append(ConfigError(
                key='SUPABASE_KEY',
                value='*' * len(supabase_key),
                message="Invalid key format"
            ))
            
        # Redis validation
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        if not redis_url.startswith(('redis://', 'rediss://')):
            if redis_url == 'redis://localhost:6379':
                warnings.append(ConfigError(
                    key='REDIS_URL',
                    value=redis_url,
                    message="Using default local Redis URL",
                    severity='warning'
                ))
            else:
                errors.append(ConfigError(
                    key='REDIS_URL',
                    value=redis_url,
                    message="Must start with redis:// or rediss://"
                ))
        
        # Log status before raising errors
        log_config_status(errors, warnings)
        
        # Raise errors if any
        if errors:
            raise ValueError(format_error_report(errors, warnings))
            
    except Exception as e:
        if not isinstance(e, ValueError):
            raise RuntimeError(f"Configuration validation failed: {str(e)}")
        raise

# Load environment variables
load_dotenv()

# Move validation before any initialization
validate_config()

# Initialize services after validation
try:
    # Initialize Supabase
    supabase: Client = create_client(
        supabase_url=os.getenv('SUPABASE_URL', ''),
        supabase_key=os.getenv('SUPABASE_KEY', '')
    )
    
    # Clean up proxy settings
    if hasattr(supabase, '_http_client'):
        if hasattr(supabase._http_client, 'proxies'):
            delattr(supabase._http_client, 'proxies')
            
    # Initialize Redis (optional in development)
    try:
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_url = f"redis://{redis_host}:{redis_port}"
        print(f"Connecting to Redis at {redis_url}")
        redis_client = redis.from_url(redis_url, decode_responses=True)
        # Test connection
        redis_client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"⚠️ Redis connection error: {e}")
        if os.getenv('FLASK_ENV') == 'development':
            print("⚠️ Redis not available - some features will be disabled")
            redis_client = None
        else:
            raise
    
except Exception as e:
    raise RuntimeError(f"Failed to initialize services: {str(e)}")

# Email settings
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Security settings
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-please-change')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'admin')

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
    'REQUIRED_CONFIG'
]
