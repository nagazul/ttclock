import os
import sys
import json
import argparse
import random
import time
import signal
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv
import requests
from datetime import datetime

# Configure logging
def setup_logging(verbosity=0):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(handler)

    script_logger = logging.getLogger(__name__)

    if verbosity == 0:
        script_logger.setLevel(logging.ERROR)
        logging.getLogger('selenium').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.ERROR)
        logging.getLogger('WDM').setLevel(logging.ERROR)
    elif verbosity == 1:
        script_logger.setLevel(logging.INFO)
        logging.getLogger('selenium').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.ERROR)
        logging.getLogger('WDM').setLevel(logging.ERROR)
    elif verbosity == 2:
        script_logger.setLevel(logging.DEBUG)
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('WDM').setLevel(logging.INFO)
    else:
        script_logger.setLevel(logging.DEBUG)
        logging.getLogger('selenium').setLevel(logging.DEBUG)
        logging.getLogger('urllib3').setLevel(logging.DEBUG)
        logging.getLogger('WDM').setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# Load environment variables
def load_environment(env_file=None):
    """Load environment variables from a custom .env file if specified, then from default .env"""
    if env_file:
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
            logger.info(f"Loaded custom environment file: {env_file}")
        else:
            logger.error(f"Custom environment file not found: {env_file}")
            sys.exit(1)
    load_dotenv()  # Load default .env file (if exists) after custom one

class TimeCheckAutomation:
    def __init__(self, quiet=True):
        self.url = os.getenv('TIMETRACKING_URL')
        self.username = os.getenv('TIMETRACKING_USERNAME')
        self.password = os.getenv('TIMETRACKING_PASSWORD')
        self.ntfy_topic = os.getenv('NTFY_TOPIC', '') if not quiet else ''
        self.driver = None
        self.wait = None

    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            try:
                logger.info("Cleaning up browser session...")
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

    def send_notification(self, message, priority='default', tags=None):
        """Send notification to ntfy.sh if topic is configured"""
        if not self.ntfy_topic:
            return

        try:
            current_time = datetime.now().strftime('%H:%M:%S')
            data = f"[{current_time}] {message}"
            headers = {
                "Priority": priority,
                "Tags": ','.join(tags) if tags else "time"
            }

            response = requests.post(
                f"https://ntfy.sh/{self.ntfy_topic}",
                data=data.encode(encoding='utf-8'),
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"Notification sent: {message}")
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")

    def setup_driver(self, max_retries=3, retry_delay=5):
        """Configure and initialize the Chrome WebDriver with retry mechanism"""
        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            try:
                logger.debug(f"Setting up Chrome options (attempt {retry_count + 1}/{max_retries})...")
                chrome_options = Options()
                chrome_options.add_argument("--disable-infobars")
                chrome_options.add_argument("--start-maximized")
                chrome_options.add_argument("--incognito")
                chrome_options.add_argument("--headless")  # Using older headless flag
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-extensions")
                chrome_options.add_argument("--dns-prefetch-disable")
                
                # Check for X11 display availability and adjust settings
                if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
                    logger.debug("No display detected, configuring for headless environment")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--disable-software-rasterizer")
                
                # Check for Chrome binary locations
                logger.debug("Checking for Chrome binary locations...")
                chrome_paths = [
                    '/usr/bin/google-chrome',
                    '/usr/bin/google-chrome-stable',
                    '/usr/bin/chromium',
                    '/usr/bin/chromium-browser'
                ]

                chrome_binary = None
                for path in chrome_paths:
                    logger.debug(f"Checking path: {path}")
                    if os.path.exists(path):
                        chrome_binary = path
                        break

                if chrome_binary:
                    chrome_options.binary_location = chrome_binary
                    logger.info(f"Using Chrome binary at: {chrome_binary}")
                    
                    # Try to get Chrome version for matching ChromeDriver
                    try:
                        chrome_version = os.popen(f'"{chrome_binary}" --version').read().strip().split()[2]
                        logger.info(f"Detected Chrome version: {chrome_version}")
                        service = Service(ChromeDriverManager(version=chrome_version.split('.')[0]).install())
                    except Exception as e:
                        logger.warning(f"Could not determine Chrome version: {e}")
                        service = Service(ChromeDriverManager().install())
                else:
                    logger.warning("Could not find Chrome binary in common locations")
                    service = Service(ChromeDriverManager().install())

                logger.debug("Initializing Chrome WebDriver...")
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.set_window_size(1920, 1080)
                
                # Set explicit timeouts
                self.driver.set_page_load_timeout(60)
                self.driver.set_script_timeout(60)
                
                logger.debug("Setting up WebDriverWait with 30 second timeout...")
                self.wait = WebDriverWait(self.driver, 30)
                
                # If we get here, initialization was successful
                return
                
            except WebDriverException as e:
                last_exception = e
                retry_count += 1
                logger.warning(f"WebDriver initialization failed (attempt {retry_count}/{max_retries}): {str(e)}")
                
                # Clean up failed driver instance if it exists
                if hasattr(self, 'driver') and self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
                    
                if retry_count < max_retries:
                    sleep_time = retry_delay * retry_count  # Increasing backoff
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to initialize WebDriver after {max_retries} attempts")
                    raise last_exception
        
        # This should never be reached due to the raise in the loop
        raise RuntimeError("Unexpected error in WebDriver initialization")

    def login(self):
        """Handle the login process"""
        try:
            logger.info("Navigating to login page...")
            self.driver.get(self.url)
            logger.debug(f"Current URL: {self.driver.current_url}")

            logger.debug("Waiting for username field...")
            username_field = self.wait.until(EC.presence_of_element_located((By.NAME, 'loginfmt')))
            logger.debug("Entering username...")
            username_field.send_keys(self.username)

            logger.debug("Waiting for next button...")
            next_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'idSIButton9')))
            logger.debug("Clicking next button...")
            next_button.click()

            logger.debug("Waiting for password field...")
            password_field = self.wait.until(EC.presence_of_element_located((By.ID, 'passwordInput')))
            logger.debug("Entering password...")
            password_field.send_keys(self.password)

            logger.debug("Waiting for submit button...")
            submit_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'submitButton')))
            logger.debug("Clicking submit button...")
            submit_button.click()

            logger.debug("Waiting for 'Stay signed in' prompt...")
            stay_signed_in = self.wait.until(EC.element_to_be_clickable((By.ID, 'idSIButton9')))
            logger.debug("Handling 'Stay signed in' prompt...")
            stay_signed_in.click()

            logger.debug("Waiting for app-root element...")
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'app-root')))
            logger.debug("Waiting for app-clock element...")
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'app-clock')))

            logger.info("Login successful and app loaded")
            logger.debug(f"Final URL after login: {self.driver.current_url}")

        except TimeoutException as e:
            logger.error(f"Timeout during login process: {str(e)}")
            logger.debug(f"Current URL at timeout: {self.driver.current_url}")
            logger.debug(f"Page source at timeout: {self.driver.page_source[:500]}...")
            raise
        except WebDriverException as e:
            logger.error(f"WebDriver error during login: {str(e)}")
            raise

    def get_time_info(self):
        """Get the time information from the page"""
        try:
            logger.info("Looking for time information...")

            rows = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.clocking-info tr"))
            )

            times = {}
            for row in rows:
                label = row.find_element(By.CLASS_NAME, "td-cell").text.strip()
                value = row.find_element(By.CLASS_NAME, "td-data").text.strip()

                if label == "Current Date":
                    day, month, year = value.split('/')
                    value = f"{year}-{month}-{day}"

                times[label] = value

            clock_buttons = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "app-clock button"))
            )

            if len(clock_buttons) < 2:
                raise ValueError("Could not find clock buttons")

            clock_in_button = clock_buttons[0]
            is_clocked_in = clock_in_button.get_attribute("disabled") is not None
            status = "Clocked In" if is_clocked_in else "Clocked Out"

            message = (
                f"Status: {status}\n"
                f"First clock in: {times.get('First clock in', 'N/A')}\n"
                f"Time worked: {times.get('All for today', 'N/A')}\n"
                f"Time left: {times.get('Time left', 'N/A')}\n"
                f"Date: {times.get('Current Date', 'N/A')}"
            )

            logger.info(message)
            self.send_notification(message, tags=["time", "check"])

            return {
                'status': status,
                'first_clock': times.get('First clock in'),
                'time_worked': times.get('All for today'),
                'time_left': times.get('Time left'),
                'date': times.get('Current Date')
            }

        except Exception as e:
            error_msg = f"Error getting time info: {str(e)}"
            logger.error(error_msg)
            self.send_notification(error_msg, priority="high", tags=["time", "error"])
            raise

    def handle_time_tracking(self, action='switch'):
        """Handle the clock in/out process"""
        try:
            logger.info("Looking for clock in/out buttons...")

            clock_buttons = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "app-clock button"))
            )

            if len(clock_buttons) < 2:
                raise ValueError("Could not find both clock in and clock out buttons")

            clock_in_button = clock_buttons[0]
            clock_out_button = clock_buttons[1]

            is_clocked_in = clock_in_button.get_attribute("disabled") is not None

            should_clock_in = {
                'in': True,
                'out': False,
                'switch': not is_clocked_in
            }.get(action)

            if should_clock_in and is_clocked_in:
                msg = "Already clocked in"
                logger.info(msg)
                self.send_notification(msg, tags=["clock", "info"])
                return
            elif not should_clock_in and not is_clocked_in:
                msg = "Already clocked out"
                logger.info(msg)
                self.send_notification(msg, tags=["clock", "info"])
                return

            if should_clock_in:
                msg = "Performing Clock In"
                logger.info(msg)
                self.send_notification(msg, tags=["clock", "in"])
                ActionChains(self.driver).move_to_element(clock_in_button).click().perform()
            else:
                msg = "Performing Clock Out"
                logger.info(msg)
                self.send_notification(msg, tags=["clock", "out"])
                ActionChains(self.driver).move_to_element(clock_out_button).click().perform()

        except Exception as e:
            error_msg = f"Error handling time tracking: {str(e)}"
            logger.error(error_msg)
            self.send_notification(error_msg, priority="high", tags=["clock", "error"])
            raise

    def run(self):
        """Run status check"""
        try:
            self.setup_driver()
            self.login()
            return self.get_time_info()
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg)
            self.send_notification(error_msg, priority="high", tags=["time", "error"])
            raise
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser session closed")

    def run_clock_action(self, action='switch', random_delay=None):
        """Run clock in/out action"""
        try:
            if random_delay:
                min_delay, max_delay = random_delay
                delay = random.uniform(min_delay * 60, max_delay * 60)
                delay_min = delay / 60
                logger.info(f"Random delay activated: waiting {delay_min:.2f} minutes...")
                time.sleep(delay)

            self.setup_driver()
            self.login()
            self.handle_time_tracking(action)
            logger.info("Time tracking operation completed successfully")
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg)
            self.send_notification(error_msg, priority="high", tags=["clock", "error"])
            raise
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser session closed")

def handle_interrupt(automation=None):
    """Handle keyboard interrupt gracefully"""
    print("\nReceived interrupt signal. Shutting down gracefully...", file=sys.stderr)
    if automation:
        automation.cleanup()
    sys.exit(0)

if __name__ == "__main__":
    # Get the full command that was executed
    command = f"Command executed: {sys.executable} {' '.join(sys.argv)}"

    parser = argparse.ArgumentParser(description='Time tracking automation')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Force disable notifications')
    parser.add_argument('-n', '--ntfy', action='store_true',
                        help='Enable notifications')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Increase verbosity (can be used up to three times: -v, -vv, or -vvv)')
    parser.add_argument('-r', '--random-delay', nargs='*', default=None, metavar=('MIN', 'MAX'),
                        help='Random delay between MIN and MAX minutes before action (defaults to 0 5 if flag present with no values)')
    parser.add_argument('--env-file', type=str,
                        help='Path to custom .env file to load environment variables from')
    parser.add_argument('action', nargs='?', choices=['in', 'out', 'switch', 'status', 'auto-out'],
                        default='status',
                        help='Specify action: "in" to clock in, "out" to clock out, "switch" to toggle, "status" to check (default), "auto-out" for auto clock-out')

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Log the command after setting up logging
    logger.info(command)

    # Handle random delay defaults
    if args.random_delay is not None:
        if args.random_delay == []:  # -r with no values
            args.random_delay = [0, 5]
        else:
            # Filter out non-numeric values and ensure we have at most 2
            numeric_values = []
            for val in args.random_delay:
                try:
                    numeric_values.append(float(val))
                except ValueError:
                    break  # Stop at first non-numeric value (likely the action)
            if len(numeric_values) == 0:
                args.random_delay = [0, 5]  # Default if no valid numbers
            elif len(numeric_values) != 2:
                parser.error("--random-delay requires exactly 2 numeric arguments (MIN MAX) when values are provided")
            else:
                args.random_delay = numeric_values

    automation = None

    try:
        # Set up signal handler for graceful shutdown
        automation = TimeCheckAutomation(quiet=args.quiet or not args.ntfy)
        signal.signal(signal.SIGINT, lambda signum, frame: handle_interrupt(automation))

        # Handle random delay if specified
        if args.random_delay:
            min_delay, max_delay = args.random_delay
            delay_secs = random.uniform(min_delay * 60, max_delay * 60)
            if not args.quiet:
                print(f"Waiting {delay_secs/60:.2f} minutes...", file=sys.stderr)
            try:
                time.sleep(delay_secs)
            except KeyboardInterrupt:
                handle_interrupt(automation)

        if args.action == 'status':
            time_info = automation.run()
            print(json.dumps(time_info, indent=2), file=sys.stdout)
        elif args.action == 'auto-out':
            # For auto-out, create automation with notifications disabled
            quiet_automation = TimeCheckAutomation(quiet=True)
            time_info = quiet_automation.run()
            
            if time_info.get('time_left') == "00:00:00" and time_info.get('status') != "Clocked Out":
                # Time is out and we need to clock out - use the real automation object
                automation.run_clock_action("out")
                logger.info("Auto clock-out completed successfully")
            else:
                logger.info("Auto-out not needed: either already clocked out or time remaining")
        else:
            automation.run_clock_action(args.action)
    except KeyboardInterrupt:
        handle_interrupt(automation)
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        if automation:
            automation.cleanup()
        sys.exit(1)
