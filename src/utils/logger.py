"""Logging configuration"""
import logging
import sys

from config.setting import settings


def setup_logger(name: str = __name__) -> logging.Logger:
    """Setup and return configured logger"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Console handler only (no file handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)

    logger.addHandler(console_handler)

    return logger
