# Empty file to make worker a package
from worker.worker import calculate_next_menu, send_menu_email

# Export these functions
__all__ = ['calculate_next_menu', 'send_menu_email']
