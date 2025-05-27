
# patient_companion/agent/utils/cloudinary.py

import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Configure Cloudinary with your credentials
# You should set these environment variables in your deployment environment
try:
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
        secure=True
    )
    logger.info("Cloudinary configured successfully")
except Exception as e:
    logger.error(f"Failed to configure Cloudinary: {str(e)}")
    # You might want to set a dummy config for development/testing
    # or raise an exception if this is critical for your application

# Export the configured cloudinary module
# This matches the structure expected in the main.py file