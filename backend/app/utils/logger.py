import logging
import sys


def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    
    # File handler (optional, good for persistent logs)
    fh = logging.FileHandler('solsniper.log')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger


# Example usage:
# logger = get_logger(__name__)
# logger.info("This is an info message.")

