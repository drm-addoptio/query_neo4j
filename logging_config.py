# logging_config.py
import logging
import google.cloud.logging
import os

# Initialize the Google Cloud Logging client
client = google.cloud.logging.Client()

# Check if running in Google Cloud environment
if os.getenv("GOOGLE_CLOUD_PROJECT"):
    # Set up logging for Google Cloud
    client.setup_logging()
else:
    # Local development: Set up console logging
    logging.basicConfig(level=logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Add the console handler to the root logger
    logger = logging.getLogger()
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

# Configure the module-level logger
logger = logging.getLogger(__name__)
