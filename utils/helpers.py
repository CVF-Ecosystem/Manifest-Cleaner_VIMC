"""Helper utility functions for VIMC Manifest Cleaner."""

from __future__ import annotations

import configparser
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd


def get_application_path() -> Path:
    """Get the directory where the application configuration and logs should be saved.
    
    Returns:
        Path to application directory
    """
    if getattr(sys, 'frozen', False):
        # Path to the directory containing the executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent.parent


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to a resource file.
    
    Looks in sys._MEIPASS if bundled as executable, or project root otherwise.
    
    Args:
        relative_path: Path relative to application root
        
    Returns:
        Absolute path to resource
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    else:
        return Path(__file__).parent.parent / relative_path


def setup_logging(
    log_filename: str = "vimc_manifest.log",
    log_level: int = logging.DEBUG
) -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        log_filename: Name of log file
        log_level: Logging level
        
    Returns:
        Configured logger
    """
    log_dir = get_application_path() / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / log_filename
    
    # Remove existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_path}")
    
    return logger


def load_ini_config(
    config_filename: str = "config.ini"
) -> Optional[configparser.ConfigParser]:
    """Load INI configuration file.
    
    Args:
        config_filename: Name of config file
        
    Returns:
        ConfigParser object or None if failed
    """
    config_path = get_application_path() / config_filename
    
    if not config_path.exists():
        logging.error(f"Config file not found: {config_path}")
        return None
    
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read(config_path, encoding='utf-8')
        logging.info(f"Loaded config from {config_path}")
        return config
    except configparser.Error as e:
        logging.error(f"Error reading config: {e}")
        return None


def is_valid_excel_file(file_path: str | Path) -> bool:
    """Check if file is a valid Excel file.
    
    Args:
        file_path: Path to file
        
    Returns:
        True if valid Excel file
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    valid_extensions = ['.xlsx', '.xls', '.xlsm']
    return file_path.suffix.lower() in valid_extensions


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_cell_value_as_str(cell_value: Any) -> str:
    """Convert cell value to string safely.
    
    Args:
        cell_value: Cell value (can be any type)
        
    Returns:
        String representation
    """
    if pd.isna(cell_value) or cell_value == '':
        return ""
    return str(cell_value).strip()


def truncate_string(s: str, max_length: int = 50) -> str:
    """Truncate string with ellipsis if too long.
    
    Args:
        s: String to truncate
        max_length: Maximum length
        
    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - 3] + "..."
