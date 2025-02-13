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

# Update logger initialization
try:
    logger = current_app.activity_logger
except (ImportError, RuntimeError):
    # Fallback for when running outside app context or Flask not available
    logger = Logger()

# Export these functions
__all__ = ['main', 'calculate_next_menu', 'send_menu_email']
