import os
import sys
import logging
import socket
import getpass
import random
import time
import hashlib
from dotenv import load_dotenv
import requests
from datetime import datetime


def setup_logging(verbosity=0):
    """Sets up logging with custom format and verbosity levels."""
    pid = os.getpid()

    if 'XID' in os.environ:
        xid = os.environ.get('XID')
    else:
        # Generate a session ID similar to the bash version
        current_time = str(time.time()).encode('utf-8')
        xid = hashlib.md5(current_time).hexdigest()[:8]

    # Format with ISO 8601 timestamp including milliseconds and timezone
    log_format = f'[XID:{xid} PID:{pid}] %(asctime)s [%(levelname)-5s] [%(hostname)s] [%(username)s] - %(message)s'

    # Create a filter to add hostname and username
    class ContextFilter(logging.Filter):
        def filter(self, record):
            record.hostname = os.environ.get('HOSTNAME',
                                              socket.gethostname().split('.')[0] if hasattr(socket, 'gethostname') else 'unknown')
            record.username = os.environ.get('USER',
                                              getpass.getuser() if hasattr(getpass, 'getuser') else 'unknown')
            return True

    # Custom formatter that adds timezone and millisecond precision
    class CustomFormatter(logging.Formatter):
        def __init__(self, fmt=None, datefmt=None, style='%', validate=True):
            super().__init__(fmt, datefmt, style, validate)
            # Map standard logging levels to 5-character display versions
            self.level_map = {
                'DEBUG': 'DEBUG',
                'INFO': 'INFO ',
                'WARNING': 'WARN ',
                'ERROR': 'ERROR',
                'CRITICAL': 'CRIT '
            }

        def format(self, record):
            # Replace levelname with our custom mapping before formatting
            if record.levelname in self.level_map:
                record.levelname = self.level_map[record.levelname]
            return super().format(record)

        def formatTime(self, record, datefmt=None):
            """Format time with ISO 8601 format including timezone and milliseconds"""
            # Get timezone offset
            if time.localtime().tm_isdst:
                tz_offset = time.altzone
            else:
                tz_offset = time.timezone

            # Convert to hours and minutes with sign
            tz_hours, tz_minutes = divmod(abs(tz_offset) // 60, 60)
            tz_sign = '+' if tz_offset <= 0 else '-'  # tz_offset is seconds west of UTC

            # Format time with milliseconds
            ct = time.localtime(record.created)
            t = time.strftime('%Y-%m-%dT%H:%M:%S', ct)
            msec = int(record.msecs)
            return f"{t}.{msec:03d}{tz_sign}{tz_hours:02d}{tz_minutes:02d}"

    # Create custom formatter
    formatter = CustomFormatter(log_format)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR) # Set root logger level high initially

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add handler with our custom formatter
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    # Add the context filter
    context_filter = ContextFilter()
    handler.addFilter(context_filter)

    root_logger.addHandler(handler)

    # Configure specific loggers based on verbosity
    script_logger = logging.getLogger('ttclock')
    playwright_logger = logging.getLogger('playwright')
    urllib3_logger = logging.getLogger('urllib3')

    # Default levels (quietest)
    script_level = logging.ERROR
    playwright_level = logging.ERROR
    urllib3_level = logging.ERROR

    if verbosity == 1: # -v
        script_level = logging.INFO
    elif verbosity == 2: # -vv
        script_level = logging.DEBUG
        playwright_level = logging.WARN
        urllib3_level = logging.WARN
    elif verbosity >= 3: # -vvv or more
        script_level = logging.DEBUG
        playwright_level = logging.DEBUG
        urllib3_level = logging.DEBUG

    script_logger.setLevel(script_level)
    playwright_logger.setLevel(playwright_level)
    urllib3_logger.setLevel(urllib3_level)

    # Ensure handlers are propagated correctly
    script_logger.propagate = True
    playwright_logger.propagate = True
    urllib3_logger.propagate = True

    return script_logger


def load_environment(env_file=None):
    """Load environment variables from ~/.ttclock.env, ./.ttclock.env, or a custom file."""
    import os.path
    from pathlib import Path

    # Define default locations
    home_config = Path.home() / ".ttclock.env"
    local_config = Path.cwd() / ".ttclock.env"

    # Try custom env_file first
    if env_file and os.path.exists(env_file):
        loaded = load_dotenv(env_file, override=True)
        if loaded:
            logging.getLogger('ttclock').info(f"Loaded custom environment file: {env_file}")
        else:
            logging.getLogger('ttclock').error(f"Custom environment file not found or empty: {env_file}")
            sys.exit(1)
    # Then try ~/.ttclock.env
    elif home_config.exists():
        loaded = load_dotenv(home_config, override=True)
        if loaded:
            logging.getLogger('ttclock').info(f"Loaded environment file: {home_config}")
        else:
            logging.getLogger('ttclock').error(f"Environment file found but empty: {home_config}")
            sys.exit(1)
    # Then try ./.ttclock.env
    elif local_config.exists():
        loaded = load_dotenv(local_config, override=True)
        if loaded:
            logging.getLogger('ttclock').info(f"Loaded environment file: {local_config}")
        else:
            logging.getLogger('ttclock').error(f"Environment file found but empty: {local_config}")
            sys.exit(1)
    else:
        logging.getLogger('ttclock').error("No environment file found at ~/.ttclock.env, ./.ttclock.env, or specified via --env-file")
        sys.exit(1)


def check_probability(chance):
    """Check probability and decide whether to execute based on chance percentage"""
    roll = random.randint(1, 100)
    logging.getLogger('ttclock').debug(f"Probability check: rolled {roll} against chance {chance}%")
    return roll <= chance


def send_notification(message, priority='default', tags=None, force=False, ntfy_topic=None, notifications_enabled=False):
    """Send notification to ntfy.sh if topic is configured and notifications are enabled.
       The 'force' parameter allows sending critical error notifications even if -q is used.
    """
    if not ntfy_topic:
        logging.getLogger('ttclock').debug("Notification sending skipped: No NTFY_TOPIC configured.")
        return
    if not notifications_enabled and not force:
        logging.getLogger('ttclock').debug(f"Notification sending skipped: Notifications disabled (quiet mode or no -n) and not forced. Message: {message[:50]}...")
        return

    try:
        # Use ISO 8601 format for notification timestamps
        now = datetime.now().astimezone() # Get timezone-aware datetime
        current_time = now.isoformat(timespec='milliseconds')

        data = f"[{current_time}] {message}"
        headers = {
            "Priority": priority,
            "Tags": ','.join(tags) if tags else "time"
        }
        full_url = f"https://ntfy.sh/{ntfy_topic}"

        logging.getLogger('ttclock').debug(f"Sending notification to {full_url} with priority '{priority}' and tags '{headers['Tags']}'")
        response = requests.post(
            full_url,
            data=data.encode(encoding='utf-8'),
            headers=headers,
            timeout=10 # Add a timeout for the request
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        logging.getLogger('ttclock').info(f"Notification sent successfully: {message[:100]}...")
    except requests.exceptions.RequestException as e:
        logging.getLogger('ttclock').error(f"Failed to send notification to {full_url}: {str(e)}")
    except Exception as e:
        logging.getLogger('ttclock').error(f"An unexpected error occurred during notification sending: {str(e)}")


def capture_screenshot(page, filename_prefix="error"):
    """Saves a screenshot of the current browser window."""
    if not page:
        logging.getLogger('ttclock').warning("Cannot capture screenshot, page is not active.")
        return

    try:
        # Create a timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.png"
        # Use a dedicated directory for screenshots if desired
        # screenshot_dir = "screenshots"
        # os.makedirs(screenshot_dir, exist_ok=True)
        # filepath = os.path.join(screenshot_dir, filename)
        filepath = filename  # Save in current directory for simplicity

        logging.getLogger('ttclock').info(f"Capturing screenshot to {filepath}")
        page.screenshot(path=filepath)
        logging.getLogger('ttclock').info(f"Screenshot saved: {filepath}")
    except Exception as e:
        logging.getLogger('ttclock').error(f"An unexpected error occurred during screenshot capture: {str(e)}")