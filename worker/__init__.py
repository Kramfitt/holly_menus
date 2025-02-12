# Empty file to make worker a package
from worker.worker import main, calculate_next_menu, send_menu_email
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Export these functions
__all__ = ['main', 'calculate_next_menu', 'send_menu_email']
