# Empty file to make worker a package
from worker.worker import main, calculate_next_menu, send_menu_email
import logging
from app.utils.logger import Logger
from flask import current_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Initialize logger
logger = Logger()  # Always use standalone logger in worker

def get_app_logger():
    """Get app logger if available"""
    try:
        return current_app.activity_logger
    except (ImportError, RuntimeError):
        return logger

# Export these functions
__all__ = ['main', 'calculate_next_menu', 'send_menu_email']
