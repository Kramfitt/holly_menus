from app import create_app
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

try:
    app = create_app()
    logging.info("Application created successfully")
except Exception as e:
    logging.error(f"Failed to create application: {str(e)}", exc_info=True)
    raise

if __name__ == "__main__":
    app.run()