"""
Logging configuration for Thermal Inspection application.
"""

import sys
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(log_file: str = 'thermal_inspection_debug.log',
                  max_bytes: int = 10*1024*1024,
                  backup_count: int = 5) -> logging.Logger:
    """
    Configure logging with console and file output.

    Args:
        log_file: Path to the debug log file
        max_bytes: Maximum size of log file before rotation (default 10MB)
        backup_count: Number of backup files to keep

    Returns:
        Logger instance for the calling module
    """
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # Fix Unicode encoding issues on Windows
    try:
        console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        # Python < 3.7 fallback
        import codecs
        console_handler.stream = codecs.getwriter('utf-8')(console_handler.stream.buffer, errors='replace')

    root_logger.addHandler(console_handler)

    # File handler
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        logging.info(f"[OK] Debug logging: {log_file}")
    except Exception as e:
        logging.warning(f"Could not create debug log: {e}")

    return logging.getLogger(__name__)
