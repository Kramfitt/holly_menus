from functools import wraps
import inspect
import json
import time
from typing import Any, Callable, Optional
from datetime import datetime
import os

from flask import current_app
from app.utils.logger import get_logger

def is_development() -> bool:
    """Check if we're running in development mode"""
    try:
        # Check for common development environment indicators
        return any([
            os.environ.get('FLASK_ENV') == 'development',
            os.environ.get('FLASK_DEBUG') == '1',
            current_app.debug if current_app else False,
            # Check if we're running locally
            os.environ.get('COMPUTERNAME', '').lower() in {'desktop', 'laptop'} or
            os.environ.get('USER', '').lower() in {'dev', 'developer'}
        ])
    except Exception:
        return False

def is_debug_mode() -> bool:
    """Check if debug mode is enabled"""
    try:
        # If in development, default to debug mode on
        if is_development():
            return True
            
        from config import redis_client
        if redis_client is None:
            return False
        return redis_client.get('debug_mode') == b'true'
    except Exception:
        return False

def debug_log(action: str, details: Any = None, timing: bool = False) -> Callable:
    """Decorator for debug logging
    
    Args:
        action: The action being performed
        details: Additional details to log
        timing: Whether to log execution time
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_debug_mode():
                return func(*args, **kwargs)
                
            start_time = time.time()
            
            # Get function details
            fn_details = {
                'function': func.__name__,
                'module': func.__module__,
                'args': str(args),
                'kwargs': str(kwargs),
                'caller': inspect.stack()[1].function
            }
            
            # Log entry
            get_logger().log_activity(
                action=f"DEBUG: {action} - Start",
                details={
                    'function_details': fn_details,
                    'additional_details': details
                },
                status="debug"
            )
            
            try:
                result = func(*args, **kwargs)
                
                # Log execution time if requested
                exec_time = None
                if timing:
                    exec_time = round((time.time() - start_time) * 1000, 2)
                
                # Log success
                get_logger().log_activity(
                    action=f"DEBUG: {action} - Complete",
                    details={
                        'function_details': fn_details,
                        'execution_time_ms': exec_time,
                        'result': str(result) if result is not None else None
                    },
                    status="debug"
                )
                
                return result
                
            except Exception as e:
                # Log error
                get_logger().log_activity(
                    action=f"DEBUG: {action} - Error",
                    details={
                        'function_details': fn_details,
                        'error': str(e),
                        'execution_time_ms': round((time.time() - start_time) * 1000, 2)
                    },
                    status="error"
                )
                raise
                
        return wrapper
    return decorator

def debug_print(*args, **kwargs):
    """Print debug information if debug mode is enabled"""
    if is_debug_mode():
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        caller = inspect.stack()[1].function
        print(f"[DEBUG {timestamp} in {caller}]", *args, **kwargs)

def format_debug_details(details: Any) -> str:
    """Format debug details for logging"""
    try:
        if isinstance(details, (dict, list)):
            return json.dumps(details, indent=2)
        return str(details)
    except Exception:
        return str(details) 