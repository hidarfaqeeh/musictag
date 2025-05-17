import os
import re
import logging

logger = logging.getLogger(__name__)

def sanitize_filename(filename):
    """
    Sanitize a filename to ensure it's safe for file system operations.
    
    Args:
        filename: The original filename
        
    Returns:
        str: A sanitized version of the filename
    """
    # Remove unsafe characters
    safe_filename = re.sub(r'[^\w\s.-]', '_', filename)
    
    # Ensure it doesn't begin with a dot or a dash
    if safe_filename.startswith(('.', '-')):
        safe_filename = f"file{safe_filename}"
    
    # Trim if too long
    if len(safe_filename) > 100:
        base, ext = os.path.splitext(safe_filename)
        safe_filename = f"{base[:95]}{ext}"
    
    return safe_filename

def ensure_temp_dir(directory):
    """
    Ensure the temporary directory exists.
    
    Args:
        directory: The directory path to ensure exists
        
    Returns:
        None
    """
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            logger.info(f"Created temporary directory: {directory}")
        except Exception as e:
            logger.error(f"Error creating temporary directory: {e}")
            # Fall back to using /tmp if possible
            if os.path.exists('/tmp'):
                logger.info("Falling back to /tmp directory")
                return '/tmp'
    return directory
