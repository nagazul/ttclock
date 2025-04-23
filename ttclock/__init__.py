import os
import sys
import json
import argparse
import random
import time
import signal
import logging
import socket
import getpass
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, JavascriptException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv
import requests
from datetime import datetime
import hashlib

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
    script_logger = logging.getLogger(__name__)
    selenium_logger = logging.getLogger('selenium')
    urllib3_logger = logging.getLogger('urllib3')
    wdm_logger = logging.getLogger('WDM') # Webdriver Manager logger

    # Default levels (quietest)
    script_level = logging.ERROR
    selenium_level = logging.ERROR
    urllib3_level = logging.ERROR
    wdm_level = logging.ERROR

    if verbosity == 1: # -v
        script_level = logging.INFO
    elif verbosity == 2: # -vv
        script_level = logging.DEBUG
        selenium_level = logging.WARN
        urllib3_level = logging.WARN
        wdm_level = logging.INFO
    elif verbosity >= 3: # -vvv or more
        script_level = logging.DEBUG
        selenium_level = logging.DEBUG
        urllib3_level = logging.DEBUG
        wdm_level = logging.DEBUG

    script_logger.setLevel(script_level)
    selenium_logger.setLevel(selenium_level)
    urllib3_logger.setLevel(urllib3_level)
    wdm_logger.setLevel(wdm_level)

    # Ensure handlers are propagated correctly
    script_logger.propagate = True
    selenium_logger.propagate = True
    urllib3_logger.propagate = True
    wdm_logger.propagate = True

# Initialize logger after setup
logger = logging.getLogger(__name__)

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
            logger.info(f"Loaded custom environment file: {env_file}")
        else:
            logger.error(f"Custom environment file not found or empty: {env_file}")
            sys.exit(1)
    # Then try ~/.ttclock.env
    elif home_config.exists():
        loaded = load_dotenv(home_config, override=True)
        if loaded:
            logger.info(f"Loaded environment file: {home_config}")
        else:
            logger.error(f"Environment file found but empty: {home_config}")
            sys.exit(1)
    # Then try ./.ttclock.env
    elif local_config.exists():
        loaded = load_dotenv(local_config, override=True)
        if loaded:
            logger.info(f"Loaded environment file: {local_config}")
        else:
            logger.error(f"Environment file found but empty: {local_config}")
            sys.exit(1)
    else:
        logger.error("No environment file found at ~/.ttclock.env, ./.ttclock.env, or specified via --env-file")
        sys.exit(1)

def check_probability(chance):
    """Check probability and decide whether to execute based on chance percentage"""
    roll = random.randint(1, 100)
    logger.debug(f"Probability check: rolled {roll} against chance {chance}%")
    return roll <= chance

class TimeCheckAutomation:
    def __init__(self, quiet=True):
        self.url = os.getenv('TIMETRACKING_URL')
        self.username = os.getenv('TIMETRACKING_USERNAME')
        self.password = os.getenv('TIMETRACKING_PASSWORD')
        self.ntfy_topic = os.getenv('NTFY_TOPIC', '') if not quiet else ''
        self.driver = None
        self.wait = None
        # Flag to control if notifications are sent (affected by -q and -n)
        self.notifications_enabled = not quiet and bool(self.ntfy_topic)
        logger.debug(f"Notifications enabled: {self.notifications_enabled} (quiet={quiet}, ntfy_topic='{self.ntfy_topic}')")

        if not self.url or not self.username or not self.password:
            logger.error("Missing required environment variables: TIMETRACKING_URL, TIMETRACKING_USERNAME, TIMETRACKING_PASSWORD")
            sys.exit(1)

    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            try:
                logger.info("Cleaning up browser session...")
                self.driver.quit()
                self.driver = None # Ensure driver is marked as None after quitting
            except Exception as e:
                logger.error(f"Error during browser cleanup: {str(e)}")

    def send_notification(self, message, priority='default', tags=None, force=False):
        """Send notification to ntfy.sh if topic is configured and notifications are enabled.
           The 'force' parameter allows sending critical error notifications even if -q is used.
        """
        if not self.ntfy_topic:
            logger.debug("Notification sending skipped: No NTFY_TOPIC configured.")
            return
        if not self.notifications_enabled and not force:
            logger.debug(f"Notification sending skipped: Notifications disabled (quiet mode or no -n) and not forced. Message: {message[:50]}...")
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
            full_url = f"https://ntfy.sh/{self.ntfy_topic}"

            logger.debug(f"Sending notification to {full_url} with priority '{priority}' and tags '{headers['Tags']}'")
            response = requests.post(
                full_url,
                data=data.encode(encoding='utf-8'),
                headers=headers,
                timeout=10 # Add a timeout for the request
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info(f"Notification sent successfully: {message[:100]}...")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send notification to {full_url}: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during notification sending: {str(e)}")

    def setup_driver(self, max_retries=3, retry_delay=5):
        """Configure and initialize the Chrome WebDriver with retry mechanism"""
        retry_count = 0
        last_exception = None

        while retry_count < max_retries:
            try:
                logger.debug(f"Setting up Chrome options (attempt {retry_count + 1}/{max_retries})...")
                chrome_options = Options()
                # Standard options
                chrome_options.add_argument("--disable-infobars")
                chrome_options.add_argument("--start-maximized")
                chrome_options.add_argument("--incognito")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-extensions")
                chrome_options.add_argument("--dns-prefetch-disable")
                chrome_options.add_argument("--disable-gpu") # Often needed in headless/server environments

                # Headless specific options
                chrome_options.add_argument("--headless=new") # Use the new headless mode
                chrome_options.add_argument("--disable-dev-shm-usage") # Crucial for Docker/CI environments
                chrome_options.add_argument("--window-size=1920,1080") # Specify window size for headless

                # Check for existing Chrome/Chromium binary
                logger.debug("Checking for Chrome binary locations...")
                chrome_paths = [
                    '/usr/bin/google-chrome',
                    '/usr/bin/google-chrome-stable',
                    '/usr/bin/chromium',
                    '/usr/bin/chromium-browser',
                    # Add paths for other OS if needed, e.g., macOS, Windows
                    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', # macOS
                ]
                chrome_binary = None
                for path in chrome_paths:
                    if os.path.exists(path):
                        chrome_binary = path
                        break

                service_instance = None
                if chrome_binary:
                    chrome_options.binary_location = chrome_binary
                    logger.info(f"Using Chrome binary at: {chrome_binary}")
                    try:
                        # Attempt to get version and use matching WebDriver
                        version_cmd = f'"{chrome_binary}" --version'
                        chrome_version_output = os.popen(version_cmd).read().strip()
                        # Extract version number (handle different output formats)
                        version_parts = chrome_version_output.split()
                        chrome_version = version_parts[-1] if version_parts else None
                        if chrome_version and '.' in chrome_version:
                            logger.info(f"Detected Chrome version: {chrome_version}")
                            # Use major version for WebDriver Manager
                            major_version = chrome_version.split('.')[0]
                            logger.info(f"Installing/Using ChromeDriver version compatible with Chrome major version {major_version}")
                            #service_instance = Service(ChromeDriverManager(driver_version=major_version).install())
                            service_instance = Service(ChromeDriverManager(chrome_version=chrome_version).install())
                        else:
                            logger.warning(f"Could not parse Chrome version from output: '{chrome_version_output}'. Falling back to latest ChromeDriver.")
                            service_instance = Service(ChromeDriverManager().install())
                    except Exception as e:
                        logger.warning(f"Could not determine Chrome version or install specific driver ({e}). Falling back to latest ChromeDriver.")
                        service_instance = Service(ChromeDriverManager().install())
                else:
                    logger.warning("Could not find Chrome binary in common locations. Attempting to use default system Chrome and latest ChromeDriver.")
                    service_instance = Service(ChromeDriverManager().install())

                logger.debug("Initializing Chrome WebDriver...")
                # Explicitly pass the service object
                self.driver = webdriver.Chrome(service=service_instance, options=chrome_options)

                # Set timeouts
                self.driver.set_page_load_timeout(60) # Increased page load timeout
                self.driver.set_script_timeout(60)  # Increased script timeout

                logger.debug("Setting up WebDriverWait with 30 second timeout...")
                self.wait = WebDriverWait(self.driver, 30) # Default wait timeout

                logger.info("WebDriver setup successful.")
                return # Exit the loop on success

            except WebDriverException as e:
                last_exception = e
                retry_count += 1
                logger.warning(f"WebDriver initialization failed (attempt {retry_count}/{max_retries}): {str(e)}")

                # Clean up any partially created driver instance
                if hasattr(self, 'driver') and self.driver:
                    try:
                        self.driver.quit()
                    except: pass # Ignore errors during cleanup
                    self.driver = None

                if retry_count < max_retries:
                    sleep_time = retry_delay * (2**(retry_count - 1)) # Exponential backoff
                    logger.info(f"Retrying WebDriver setup in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to initialize WebDriver after {max_retries} attempts.")
                    # Send a critical notification if setup fails completely
                    self.send_notification(f"Critical Error: Failed to initialize WebDriver after {max_retries} attempts. Last error: {str(last_exception)}", priority="high", tags=["setup", "error"], force=True)
                    raise last_exception # Re-raise the last exception
            except Exception as e:
                 # Catch other potential errors during setup
                 logger.error(f"An unexpected error occurred during WebDriver setup: {str(e)}")
                 self.send_notification(f"Critical Error: Unexpected error during WebDriver setup: {str(e)}", priority="high", tags=["setup", "error"], force=True)
                 raise # Re-raise the exception

        # This part should ideally not be reached if the loop logic is correct
        logger.critical("Exited WebDriver setup loop unexpectedly.")
        raise RuntimeError("Unexpected exit from WebDriver setup routine.")


    def login(self):
        """Handle the login process"""
        if not self.driver or not self.wait:
             logger.error("WebDriver not initialized before calling login.")
             raise RuntimeError("WebDriver not initialized.")
        try:
            logger.info(f"Navigating to login page: {self.url}")
            self.driver.get(self.url)
            logger.debug(f"Current URL after navigation: {self.driver.current_url}")

            # --- Microsoft Login Flow ---
            # 1. Enter username
            logger.debug("Waiting for username field (loginfmt)...")
            username_field = self.wait.until(EC.presence_of_element_located((By.NAME, 'loginfmt')), "Timed out waiting for username field")
            logger.debug("Entering username...")
            username_field.send_keys(self.username)

            # 2. Click Next
            logger.debug("Waiting for Next button (idSIButton9)...")
            next_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'idSIButton9')), "Timed out waiting for Next button after username")
            logger.debug("Clicking Next button...")
            next_button.click()

            # 3. Enter password
            logger.debug("Waiting for password field (passwordInput)...")
            # Use visibility_of_element_located for password field as it might be hidden initially
            password_field = self.wait.until(EC.visibility_of_element_located((By.ID, 'passwordInput')), "Timed out waiting for password field")
            logger.debug("Entering password...")
            password_field.send_keys(self.password)

            # 4. Click Submit (Sign in)
            logger.debug("Waiting for Submit button (submitButton)...")
            submit_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'submitButton')), "Timed out waiting for Submit button after password")
            logger.debug("Clicking Submit button...")
            submit_button.click()

            # 5. Handle 'Stay signed in?' prompt
            logger.debug("Waiting for 'Stay signed in?' prompt (idSIButton9)...")
            try:
                # This prompt might not always appear, use a shorter timeout
                stay_signed_in_wait = WebDriverWait(self.driver, 10)
                stay_signed_in_button = stay_signed_in_wait.until(
                    EC.element_to_be_clickable((By.ID, 'idSIButton9')),
                    "Timed out waiting for 'Stay signed in?' button (optional)"
                )
                logger.debug("Handling 'Stay signed in?' prompt by clicking Yes...")
                stay_signed_in_button.click()
            except TimeoutException:
                logger.debug("'Stay signed in?' prompt not detected or timed out, continuing...")

            # --- Wait for Application Load ---
            logger.debug("Waiting for main application elements (app-root and app-clock)...")
            # Wait for a reliable element indicating the app has loaded
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'app-root')), "Timed out waiting for app-root tag")
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'app-clock')), "Timed out waiting for app-clock tag")
            # Add a small explicit wait to allow dynamic content to potentially load
            time.sleep(2)

            logger.info("Login successful and application appears loaded.")
            logger.debug(f"Final URL after login: {self.driver.current_url}")

        except TimeoutException as e:
            page_title = self.driver.title if self.driver else "N/A"
            current_url = self.driver.current_url if self.driver else "N/A"
            error_msg = f"Timeout during login process at URL {current_url} (Title: {page_title}). Element not found: {e.msg}"
            logger.error(error_msg)
            # Try to capture screenshot on timeout
            self.capture_screenshot("login_timeout_error")
            logger.debug(f"Page source at timeout (first 1000 chars): {self.driver.page_source[:1000]}...")
            self.send_notification(f"Login Error: Timeout - {e.msg}", priority="high", tags=["login", "error", "timeout"], force=True)
            raise TimeoutException(error_msg) from e # Re-raise with more context
        except WebDriverException as e:
            logger.error(f"WebDriver error during login: {str(e)}")
            self.capture_screenshot("login_webdriver_error")
            self.send_notification(f"Login Error: WebDriverException - {str(e)}", priority="high", tags=["login", "error", "webdriver"], force=True)
            raise # Re-raise the original exception
        except Exception as e:
            logger.error(f"An unexpected error occurred during login: {str(e)}")
            self.capture_screenshot("login_unexpected_error")
            self.send_notification(f"Login Error: Unexpected - {str(e)}", priority="high", tags=["login", "error", "unexpected"], force=True)
            raise # Re-raise the original exception

    def remove_blocking_modal(self):
        """Checks for and removes the specific blocking modal using JavaScript."""
        if not self.driver:
            logger.warning("Attempted to remove modal, but driver is not initialized.")
            return

        logger.debug("Checking for blocking modal...")
        script = """
            var backdrop = document.querySelector('div.modal-backdrop');
            var container = document.querySelector('div.modal-container');
            var removed = false;
            if (backdrop) {
                backdrop.remove();
                console.log('Removed modal backdrop.');
                removed = true;
            }
            if (container) {
                // You might need to adjust the selector if the container class isn't unique enough
                // For example: document.querySelector('app-root div.modal-container');
                container.remove();
                console.log('Removed modal container.');
                removed = true;
            }
            return removed;
        """
        try:
            removed = self.driver.execute_script(script)
            if removed:
                logger.info("Detected and removed blocking modal popup.")
                # Add a small pause to allow the UI to potentially readjust
                time.sleep(1)
            else:
                logger.debug("Blocking modal not found.")
        except JavascriptException as e:
            logger.error(f"JavaScript error while trying to remove modal: {e.msg}")
        except WebDriverException as e:
            logger.error(f"WebDriver error while trying to remove modal: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while removing modal: {str(e)}")


    def get_time_info(self):
        """Get the time information from the page"""
        if not self.driver or not self.wait:
             logger.error("WebDriver not initialized before calling get_time_info.")
             raise RuntimeError("WebDriver not initialized.")
        try:
            logger.info("Attempting to retrieve time information...")

            # Wait for the table containing the info to be present
            logger.debug("Waiting for clocking info table...")
            info_table = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.clocking-info")),
                "Timed out waiting for the clocking info table"
            )

            # Find all rows within the table body
            logger.debug("Locating rows in the table...")
            rows = info_table.find_elements(By.CSS_SELECTOR, "tbody tr") # More specific selector
            if not rows:
                 logger.warning("No rows found within the clocking info table body.")
                 # Attempt to capture screenshot if table structure is unexpected
                 self.capture_screenshot("get_time_info_no_rows")
                 # Return empty dict or raise error depending on desired behavior
                 return {} # Or raise ValueError("No data rows found in time info table")

            times = {}
            logger.debug(f"Processing {len(rows)} rows...")
            for i, row in enumerate(rows):
                try:
                    # Find label and value cells within the row
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        label = cells[0].text.strip()
                        value = cells[1].text.strip()
                        logger.debug(f"Row {i}: Label='{label}', Value='{value}'")

                        # Standardize date format if found
                        if label == "Current Date" and value:
                            try:
                                # Assuming DD/MM/YYYY format
                                day, month, year = value.split('/')
                                value = f"{year}-{month}-{day}" # Convert to YYYY-MM-DD
                            except ValueError:
                                logger.warning(f"Could not parse date '{value}' in expected DD/MM/YYYY format.")
                                # Keep original value if parsing fails

                        times[label] = value
                    else:
                        logger.warning(f"Row {i} does not have at least 2 cells (td elements). Skipping row.")

                except Exception as e:
                    logger.warning(f"Error processing row {i}: {str(e)}. Skipping row.")
                    continue # Skip to the next row if an error occurs

            # Determine Clock In/Out Status
            logger.debug("Checking clock button status...")
            try:
                # Wait for the buttons to be present within app-clock
                clock_buttons_container = self.wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "app-clock")),
                    "Timed out waiting for app-clock container"
                )
                clock_buttons = clock_buttons_container.find_elements(By.TAG_NAME, "button")

                if len(clock_buttons) >= 2:
                    clock_in_button = clock_buttons[0]
                    # Check if the clock-in button is disabled (means user is clocked in)
                    is_clocked_in = clock_in_button.get_attribute("disabled") is not None
                    status = "Clocked In" if is_clocked_in else "Clocked Out"
                    logger.debug(f"Determined status based on button state: {status}")
                else:
                    logger.warning(f"Expected at least 2 clock buttons, found {len(clock_buttons)}. Cannot determine status accurately.")
                    status = "Unknown"
                    self.capture_screenshot("get_time_info_missing_buttons")

            except TimeoutException:
                logger.error("Timed out waiting for clock buttons to determine status.")
                status = "Unknown (Timeout)"
                self.capture_screenshot("get_time_info_button_timeout")
            except Exception as e:
                 logger.error(f"Error determining clock status from buttons: {str(e)}")
                 status = "Unknown (Error)"
                 self.capture_screenshot("get_time_info_button_error")


            # Prepare result dictionary
            result = {
                'status': status,
                'first_clock': times.get('First clock in'),
                'time_worked': times.get('All for today'), # Key based on user's script
                'time_left': times.get('Time left'),
                'date': times.get('Current Date') # Already formatted to YYYY-MM-DD
            }

            # Log the retrieved information
            log_message = (
                f"Retrieved time info: Status='{result['status']}', "
                f"First Clock='{result['first_clock']}', Worked='{result['time_worked']}', "
                f"Left='{result['time_left']}', Date='{result['date']}'"
            )
            logger.info(log_message)

            # Return the dictionary - Notification is handled by the calling method (run or run_clock_action)
            return result

        except TimeoutException as e:
            error_msg = f"Timeout error while getting time info: {e.msg}"
            logger.error(error_msg)
            self.capture_screenshot("get_time_info_timeout_error")
            self.send_notification(f"Error getting time info: Timeout - {e.msg}", priority="high", tags=["time", "error", "timeout"], force=True)
            raise TimeoutException(error_msg) from e
        except NoSuchElementException as e:
            error_msg = f"Could not find expected element while getting time info: {e.msg}"
            logger.error(error_msg)
            self.capture_screenshot("get_time_info_no_element_error")
            self.send_notification(f"Error getting time info: Element not found - {e.msg}", priority="high", tags=["time", "error", "missing_element"], force=True)
            raise NoSuchElementException(error_msg) from e
        except Exception as e:
            error_msg = f"An unexpected error occurred getting time info: {str(e)}"
            logger.error(error_msg, exc_info=True) # Log traceback for unexpected errors
            self.capture_screenshot("get_time_info_unexpected_error")
            self.send_notification(f"Error getting time info: Unexpected - {str(e)}", priority="high", tags=["time", "error", "unexpected"], force=True)
            raise # Re-raise the original exception


    def handle_time_tracking(self, action='switch'):
        """Handle the clock in/out process based on the specified action."""
        if not self.driver or not self.wait:
             logger.error("WebDriver not initialized before calling handle_time_tracking.")
             raise RuntimeError("WebDriver not initialized.")
        try:
            logger.info(f"Attempting to handle time tracking action: '{action}'")

            # --- Locate Clock Buttons ---
            logger.debug("Waiting for clock buttons within app-clock...")
            try:
                clock_buttons_container = self.wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "app-clock")),
                    "Timed out waiting for app-clock container for buttons"
                )
                # Ensure buttons inside are interactable
                clock_buttons = self.wait.until(
                    EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "app-clock button")),
                    "Timed out waiting for clock buttons to be visible"
                )
            except TimeoutException as e:
                logger.error(f"Could not find or wait for clock buttons: {e.msg}")
                self.capture_screenshot("handle_time_tracking_button_timeout")
                raise TimeoutException(f"Failed to find clock buttons: {e.msg}") from e

            if len(clock_buttons) < 2:
                logger.error(f"Expected at least 2 clock buttons, found {len(clock_buttons)}.")
                self.capture_screenshot("handle_time_tracking_missing_buttons")
                raise ValueError(f"Could not find both clock buttons (found {len(clock_buttons)})")

            clock_in_button = clock_buttons[0]
            clock_out_button = clock_buttons[1]

            # --- Determine Current Status and Target Action ---
            is_clocked_in = clock_in_button.get_attribute("disabled") is not None
            current_status = "Clocked In" if is_clocked_in else "Clocked Out"
            logger.debug(f"Current status determined as: {current_status}")

            target_action = None # 'clock_in', 'clock_out', or None (no action needed)
            if action == 'in':
                if not is_clocked_in:
                    target_action = 'clock_in'
                else:
                    logger.info("Action 'in' requested, but already clocked in. No action taken.")
            elif action == 'out':
                if is_clocked_in:
                    target_action = 'clock_out'
                else:
                    logger.info("Action 'out' requested, but already clocked out. No action taken.")
            elif action == 'switch':
                target_action = 'clock_out' if is_clocked_in else 'clock_in'
                logger.info(f"Action 'switch' requested. Will attempt to {target_action.replace('_', ' ')}.")
            else:
                logger.warning(f"Invalid action '{action}' passed to handle_time_tracking. No action taken.")
                return False # Indicate no action was performed

            # --- Perform Action if Needed ---
            if target_action:
                button_to_click = clock_in_button if target_action == 'clock_in' else clock_out_button
                action_name = "Clock In" if target_action == 'clock_in' else "Clock Out"
                logger.info(f"Performing action: {action_name}")

                try:
                    # Use JavaScript click as a fallback if regular click fails
                    logger.debug(f"Attempting to click {action_name} button...")
                    # Ensure the button is clickable before attempting
                    self.wait.until(EC.element_to_be_clickable(button_to_click), f"Timed out waiting for {action_name} button to be clickable")
                    # ActionChains can be more reliable sometimes
                    ActionChains(self.driver).move_to_element(button_to_click).click().perform()
                    logger.debug(f"{action_name} button clicked successfully.")

                    # Add a small delay to allow the UI to update after the click
                    time.sleep(3) # Adjust as needed

                    # --- Verify Action and Send Notification ---
                    # Re-fetch time info to confirm the action and get updated times
                    logger.info("Fetching updated time info after action...")
                    time_info = self.get_time_info() # This already has error handling

                    # Verify the status change (optional but good practice)
                    new_status = time_info.get('status', 'Unknown')
                    expected_status = "Clocked In" if target_action == 'clock_in' else "Clocked Out"
                    if new_status == expected_status:
                        logger.info(f"Action {action_name} confirmed. New status: {new_status}")
                    elif new_status == "Unknown":
                         logger.warning(f"Action {action_name} performed, but could not confirm new status.")
                    else:
                        logger.warning(f"Action {action_name} performed, but status is unexpectedly '{new_status}' (expected '{expected_status}').")
                        self.capture_screenshot(f"{target_action}_status_mismatch")


                    # Send notification based on the action performed
                    if target_action == 'clock_in':
                        notification_msg = (
                            f"Successfully clocked in.\n"
                            f"Time worked today: {time_info.get('time_worked', 'N/A')}\n"
                            f"Time left: {time_info.get('time_left', 'N/A')}"
                        )
                        self.send_notification(notification_msg, tags=["clock", "in", "success"])
                    else: # clock_out
                        notification_msg = (
                            f"Successfully clocked out.\n"
                            f"Total time worked today: {time_info.get('time_worked', 'N/A')}"
                        )
                        self.send_notification(notification_msg, tags=["clock", "out", "success"])

                    return True # Indicate action was successfully performed

                except TimeoutException as e:
                    error_msg = f"Timeout while trying to click {action_name} button or waiting after click: {e.msg}"
                    logger.error(error_msg)
                    self.capture_screenshot(f"{target_action}_click_timeout")
                    self.send_notification(f"Error during {action_name}: Timeout - {e.msg}", priority="high", tags=["clock", "error", "timeout"], force=True)
                    raise TimeoutException(error_msg) from e
                except WebDriverException as e:
                    # Catch potential issues like element not interactable
                    error_msg = f"WebDriver error performing {action_name}: {str(e)}"
                    logger.error(error_msg)
                    self.capture_screenshot(f"{target_action}_click_webdriver_error")
                    self.send_notification(f"Error during {action_name}: WebDriverException - {str(e)}", priority="high", tags=["clock", "error", "webdriver"], force=True)
                    raise # Re-raise
                except Exception as e:
                    # Catch errors during the get_time_info call after action
                    error_msg = f"Error after performing {action_name} (likely during status update check): {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    # Notification for the original error is likely already sent by get_time_info
                    # Optionally send another one indicating context
                    self.send_notification(f"Error after {action_name}: {str(e)}", priority="high", tags=["clock", "error", "post_action"], force=True)
                    raise # Re-raise
            else:
                # Case where no action was needed (e.g., already clocked in when 'in' was requested)
                return False # Indicate no action was performed

        except Exception as e:
            # Catch errors before the action is attempted (e.g., finding buttons)
            error_msg = f"An unexpected error occurred in handle_time_tracking before action '{action}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.capture_screenshot("handle_time_tracking_unexpected_error")
            self.send_notification(f"Error handling time tracking ({action}): {str(e)}", priority="high", tags=["clock", "error", "unexpected"], force=True)
            raise # Re-raise


    def run_status_check(self):
        """Runs only the status check part of the automation."""
        try:
            self.setup_driver()
            self.login()
            self.remove_blocking_modal() # Check for and remove modal after login
            time_info = self.get_time_info() # Retrieve status

            # Send notification specifically for status check success if enabled
            if self.notifications_enabled:
                 status_message = (
                     f"Status check successful.\n"
                     f"Current status: {time_info.get('status', 'Unknown')}\n"
                     f"Time worked: {time_info.get('time_worked', 'N/A')}\n"
                     f"Time left: {time_info.get('time_left', 'N/A')}"
                 )
                 self.send_notification(status_message, tags=["time", "check", "success"])

            return time_info # Return the dictionary containing time info
        except (TimeoutException, WebDriverException, NoSuchElementException, ValueError, RuntimeError) as e:
            # Errors during setup, login, or get_time_info are already logged and notified
            logger.error(f"Status check failed due to: {str(e)}")
            # No need to send another notification here, previous steps handle it.
            raise # Re-raise the exception to be caught by the main loop
        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"An unexpected error occurred during status check: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.send_notification(error_msg, priority="high", tags=["time", "check", "error", "unexpected"], force=True)
            raise
        finally:
            self.cleanup() # Ensure browser is closed


    def run_clock_action(self, action='switch'):
        """Runs the clock in/out action part of the automation."""
        try:
            self.setup_driver()
            self.login()
            self.remove_blocking_modal() # Check for and remove modal after login
            action_performed = self.handle_time_tracking(action)

            if action_performed:
                logger.info(f"Clock action '{action}' completed successfully.")
                # Notification is already sent by handle_time_tracking on success
            else:
                logger.info(f"Clock action '{action}' resulted in no operation (e.g., already in desired state).")
                # Optionally send a notification indicating no action was needed, if desired
                # self.send_notification(f"Clock action '{action}' not needed.", tags=["clock", "no_op"])

        except (TimeoutException, WebDriverException, NoSuchElementException, ValueError, RuntimeError) as e:
            # Errors during setup, login, or handle_time_tracking are logged and notified
            logger.error(f"Clock action '{action}' failed due to: {str(e)}")
            # No need to send another notification here.
            raise # Re-raise exception
        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"An unexpected error occurred during clock action '{action}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.send_notification(error_msg, priority="high", tags=["clock", "action", "error", "unexpected"], force=True)
            raise
        finally:
            self.cleanup() # Ensure browser is closed

    def run_auto_out(self):
        """Checks status and clocks out automatically if time left is 00:00:00."""
        try:
            self.setup_driver()
            self.login()
            self.remove_blocking_modal() # Check for and remove modal after login

            logger.info("Running auto-out check...")
            time_info = self.get_time_info()

            status = time_info.get('status')
            time_left = time_info.get('time_left')

            logger.debug(f"Auto-out check: Status='{status}', Time Left='{time_left}'")

            if status == "Clocked In" and time_left == "00:00:00":
                logger.info("Conditions met for auto clock-out (Clocked In and Time Left is 00:00:00).")
                # Use the existing browser session to clock out
                action_performed = self.handle_time_tracking("out")
                if action_performed:
                    logger.info("Auto clock-out performed successfully.")
                    # Notification sent by handle_time_tracking
                else:
                    # This case should ideally not happen if status was correct, but log it.
                    logger.warning("Auto clock-out condition met, but handle_time_tracking reported no action was taken.")
            elif status == "Clocked Out":
                logger.info("Auto-out check: Already clocked out. No action needed.")
            elif status == "Clocked In":
                logger.info(f"Auto-out check: Still clocked in, but time left is '{time_left}'. No action needed.")
            else:
                 logger.warning(f"Auto-out check: Status is '{status}'. Cannot determine if auto-out is needed.")

        except (TimeoutException, WebDriverException, NoSuchElementException, ValueError, RuntimeError) as e:
            logger.error(f"Auto-out check failed due to: {str(e)}")
            # Error notifications handled in underlying methods
            raise
        except Exception as e:
            error_msg = f"An unexpected error occurred during auto-out check: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.send_notification(error_msg, priority="high", tags=["clock", "auto_out", "error", "unexpected"], force=True)
            raise
        finally:
            self.cleanup() # Ensure browser is closed

    def capture_screenshot(self, filename_prefix="error"):
        """Saves a screenshot of the current browser window."""
        if not self.driver:
            logger.warning("Cannot capture screenshot, WebDriver is not active.")
            return

        try:
            # Create a timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.png"
            # Use a dedicated directory for screenshots if desired
            # screenshot_dir = "screenshots"
            # os.makedirs(screenshot_dir, exist_ok=True)
            # filepath = os.path.join(screenshot_dir, filename)
            filepath = filename # Save in current directory for simplicity

            logger.info(f"Capturing screenshot to {filepath}...")
            self.driver.save_screenshot(filepath)
            logger.info(f"Screenshot saved: {filepath}")
        except WebDriverException as e:
            logger.error(f"Failed to capture screenshot: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during screenshot capture: {str(e)}")


# --- Global Signal Handler ---
# Keep track of the current automation instance for cleanup
current_automation_instance = None

def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    signal_name = signal.Signals(signum).name
    print(f"\nReceived signal {signal_name} ({signum}). Shutting down gracefully...", file=sys.stderr)
    logger.warning(f"Received signal {signal_name} ({signum}). Initiating graceful shutdown.")
    if current_automation_instance:
        current_automation_instance.cleanup()
    logger.info("Cleanup complete. Exiting.")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler) # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # kill command


# --- Argument Parsing ---
def parse_arguments():
    """Parse command line arguments with improved handling for optional args."""
    parser = argparse.ArgumentParser(
        description='Automates interactions with a time tracking website.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help
    )

    # Action argument (positional or optional)
    # Using a subparsers approach might be cleaner for distinct actions,
    # but sticking to the original structure for now.
    parser.add_argument(
        'action',
        nargs='?', # Makes the action optional
        choices=['in', 'out', 'switch', 'status', 'auto-out'],
        default='status', # Default action if none is provided
        help='The primary action to perform: clock "in", clock "out", "switch" state, check "status", or perform "auto-out" based on time left.'
    )

    # Notification control
    notification_group = parser.add_mutually_exclusive_group()
    notification_group.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress all non-error output and disable notifications (overrides -n and NTFY_TOPIC).'
    )
    notification_group.add_argument(
        '-n', '--ntfy',
        action='store_true',
        help='Enable notifications via ntfy.sh (requires NTFY_TOPIC env var). Ignored if -q is used.'
    )

    # Verbosity
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase logging verbosity (-v: INFO, -vv: DEBUG script/WARN libs, -vvv: DEBUG all). Errors are always logged.'
    )

    # Random Delay
    parser.add_argument(
        '-r', '--random-delay',
        nargs='*', # 0 or more arguments
        type=float,
        metavar=('MIN', 'MAX'),
        help='Wait for a random duration between MIN and MAX minutes before executing the action. If only MIN is given, MAX is MIN+5. If no values are given, defaults to 0-5 minutes.'
    )

    # Probability
    parser.add_argument(
        '-p', '--probability', '--prob',
        type=int,
        metavar='PERCENT',
        default=100, # Default to 100% probability (always run)
        help='An integer percentage (0-100) representing the chance the script will execute the main action. Default is 100.'
    )

    # Environment File
    parser.add_argument(
        '--env-file',
        type=str,
        metavar='FILEPATH',
        help='Path to a custom .env file to load environment variables from (overrides default .env).'
    )

    # --- Argument Validation and Processing ---
    args = parser.parse_args()

    # Validate probability
    if not (0 <= args.probability <= 100):
        parser.error("Probability must be an integer between 0 and 100.")

    # Process random_delay
    if args.random_delay is not None: # Check if the flag was present
        if len(args.random_delay) == 0:
            args.random_delay = (0.0, 5.0) # Default range 0-5 mins
        elif len(args.random_delay) == 1:
            min_delay = args.random_delay[0]
            if min_delay < 0: parser.error("Minimum delay cannot be negative.")
            args.random_delay = (min_delay, min_delay + 5.0) # Single value means min to min+5
        elif len(args.random_delay) == 2:
            min_delay, max_delay = args.random_delay
            if min_delay < 0 or max_delay < 0: parser.error("Delay values cannot be negative.")
            if min_delay > max_delay: parser.error("Minimum delay cannot be greater than maximum delay.")
            args.random_delay = (min_delay, max_delay) # Use provided range
        else:
            parser.error("Argument --random-delay: expected 0, 1, or 2 values.")
    # If --random-delay was not provided, args.random_delay remains None

    return args


# --- Main Execution Logic ---
def main():
    """Main execution function"""
    global current_automation_instance # Allow modification of the global instance tracker

    args = parse_arguments()
    setup_logging(args.verbose if not args.quiet else -1) # Pass -1 or similar if quiet to ensure minimal logging

    # Log the command execution details
    command_line = f"{sys.executable} {' '.join(sys.argv)}"
    logger.info(f"Script started. Command: {command_line}")
    logger.debug(f"Parsed arguments: {args}")

    load_environment(args.env_file)

    # --- Probability Check ---
    if args.probability < 100:
        logger.info(f"Checking probability: {args.probability}% chance to execute.")
        if not check_probability(args.probability):
            logger.info(f"Skipping execution based on probability check (rolled > {args.probability}).")
            sys.exit(0) # Exit cleanly
        else:
            logger.info(f"Proceeding with execution based on probability check (rolled <= {args.probability}).")
    else:
        logger.debug("Probability is 100%, execution will proceed.")


    # --- Random Delay ---
    if args.random_delay:
        min_delay, max_delay = args.random_delay
        delay_secs = random.uniform(min_delay * 60, max_delay * 60)
        logger.info(f"Applying random delay: waiting for {delay_secs:.2f} seconds ({delay_secs/60:.2f} minutes)...")
        try:
            time.sleep(delay_secs)
        except KeyboardInterrupt:
            # signal_handler will be invoked automatically by the system
            logger.warning("Delay interrupted by user.")
            # The signal handler should exit, but add an explicit exit just in case.
            sys.exit(1)


    # --- Execute Action ---
    automation = None # Initialize to None
    exit_code = 0
    try:
        # Determine notification enablement based on args and env var
        # Quiet flag takes precedence
        enable_notifications = not args.quiet and args.ntfy and bool(os.getenv('NTFY_TOPIC'))
        automation = TimeCheckAutomation(quiet=args.quiet or not enable_notifications)
        current_automation_instance = automation # Register instance for signal handler

        logger.info(f"Executing action: {args.action}")

        if args.action == 'status':
            time_info = automation.run_status_check()
            # Print JSON output for status check
            try:
                 print(json.dumps(time_info, indent=2), file=sys.stdout)
            except TypeError as e:
                 logger.error(f"Failed to serialize time_info to JSON: {e}")
                 print(f"Raw time info: {time_info}", file=sys.stderr) # Print raw dict as fallback
        elif args.action == 'auto-out':
            automation.run_auto_out()
        elif args.action in ['in', 'out', 'switch']:
            automation.run_clock_action(args.action)
        else:
            # This case should not be reachable due to argparse choices
            logger.error(f"Internal error: Unhandled action '{args.action}'")
            exit_code = 2

        logger.info(f"Action '{args.action}' completed.")

    except (TimeoutException, WebDriverException, NoSuchElementException, ValueError, RuntimeError) as e:
        logger.critical(f"Script execution failed: {type(e).__name__} - {str(e)}")
        # Specific error logging and notifications are handled within the methods
        exit_code = 1 # Indicate failure
    except KeyboardInterrupt:
        logger.warning("Script execution interrupted by user (main loop).")
        # Signal handler should manage cleanup and exit.
        exit_code = 130 # Standard exit code for SIGINT
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred in main execution: {str(e)}", exc_info=True)
        # Send a final notification for unexpected errors if possible
        if automation:
             automation.send_notification(f"Critical script error: {str(e)}", priority="high", tags=["main", "error", "unexpected"], force=True)
        exit_code = 1 # Indicate failure
    finally:
        # Ensure cleanup runs even if automation object wasn't fully initialized in edge cases
        if current_automation_instance and current_automation_instance.driver:
            logger.debug("Performing final cleanup check in main finally block.")
            current_automation_instance.cleanup()
        current_automation_instance = None # Deregister instance

    logger.info(f"Script finished with exit code {exit_code}.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
