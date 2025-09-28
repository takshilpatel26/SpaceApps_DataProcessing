"""Input validation decorators and functions."""

import functools
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def validate_file_exists(func):
    """Decorator to validate input file exists."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check args for file paths
        for i, arg in enumerate(args):
            if isinstance(arg, (str, Path)) and str(arg).endswith(('.zip', '.tif')):
                if not Path(arg).exists():
                    raise FileNotFoundError(f"Input file not found: {arg}")
        return func(*args, **kwargs)
    return wrapper

def validate_output_dir(func):
    """Decorator to validate and create output directory."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check args for directory paths
        for arg in args:
            if isinstance(arg, (str, Path)):
                path = Path(arg)
                if not str(path).endswith(('.zip', '.tif', '.nc')):  # Likely a directory
                    path.mkdir(parents=True, exist_ok=True)
        return func(*args, **kwargs)
    return wrapper
