"""
Logging Configuration
Configures specialized loggers for Application, TCP connections, and GPS Telemetry.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
TCP_LOG_DIR = LOGS_DIR / "tcp_logs"
GPS_LOG_DIR = LOGS_DIR / "gps_logs"

TCP_LOG_DIR.mkdir(parents=True, exist_ok=True)
GPS_LOG_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str, log_file: Path, level=logging.INFO, to_console=True) -> logging.Logger:
    """Creates a configured rotating file logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if reloaded
    if logger.handlers:
        return logger

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt=DATE_FORMAT)

    # Rotating File Handler (10MB per file, max 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    if to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# Instantiate standard loggers
app_logger = setup_logger("custody_app", LOGS_DIR / "app.log")
tcp_logger = setup_logger("custody_tcp", TCP_LOG_DIR / "tcp.log")
gps_logger = setup_logger("custody_gps", GPS_LOG_DIR / "gps.log")

