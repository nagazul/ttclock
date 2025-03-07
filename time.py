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
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv
import requests
from datetime import datetime
import hashlib

def setup_logging(verbosity=0):
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
    class ISOFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            ct = self.converter(record.created)
            # Get timezone offset
            if time.localtime().tm_isdst:
                tz_offset = time.altzone
            else:
                tz_offset = time.timezone
            # Convert to hours and minutes with sign
            tz_hours, tz_minutes = divmod(abs(tz_offset) // 60, 60)
            tz_sign = '+' if tz_offset <= 0 else '-'  # tz_offset is seconds west of UTC
            
            # Format time with milliseconds
            t = time.strftime('%Y-%m-%dT%H:%M:%S', ct)
            msec = int(record.msecs)
            return f"{t}.{msec:03d}{tz_sign}{tz_hours:02d}{tz_minutes:02d}"
    
    # Create custom formatter
    formatter = ISOFormatter(log_format)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    
    # Add the context filter
    context_filter = ContextFilter()
    handler.addFilter(context_filter)
    
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
        logging.getLogger('selenium').setLevel(logging.WARN)
        logging.getLogger('urllib3').setLevel(logging.WARN)
        logging.getLogger('WDM').setLevel(logging.INFO)
    else:
        script_logger.setLevel(logging.DEBUG)
        logging.getLogger('selenium').setLevel(logging.DEBUG)
        logging.getLogger('urllib3').setLevel(logging.DEBUG)
        logging.getLogger('WDM').setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

def load_environment(env_file=None):
    """Load environment variables from a custom .env file if specified, then from default .env"""
    if env_file:
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
            logger.info(f"Loaded custom environment file: {env_file}")
        else:
            logger.error(f"Custom environment file not found: {env_file}")
            sys.exit(1)
    load_dotenv()

class TimeCheckAutomation:
    def __init__(self, quiet=True):
        self.url = os.getenv('TIMETRACKING_URL')
        self.username = os.getenv('TIMETRACKING_USERNAME')
        self.password = os.getenv('TIMETRACKING_PASSWORD')
        self.ntfy_topic = os.getenv('NTFY_TOPIC', '') if not quiet else ''
        self.driver = None
        self.wait = None
        self.send_success_notifications_only = True  # New flag to control notification behavior

    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            try:
                logger.info("Cleaning up browser session...")
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

    def send_notification(self, message, priority='default', tags=None, force=False):
        """Send notification to ntfy.sh if topic is configured
        The force parameter allows bypassing the success-only restriction for critical notifications
        """
        if not self.ntfy_topic:
            return
            
        # Always send success notifications and high priority notifications
        # The self.send_success_notifications_only flag now controls when notifications
        # are created, not whether they're sent once created
        
        try:
            # Update to use ISO 8601 format for notification timestamps
            now = datetime.now()
            tz_offset_minutes = now.astimezone().utcoffset().total_seconds() / 60
            tz_sign = '+' if tz_offset_minutes >= 0 else '-'
            tz_hours, tz_minutes = divmod(abs(int(tz_offset_minutes)), 60)
            current_time = f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{now.microsecond//1000:03d}{tz_sign}{tz_hours:02d}{tz_minutes:02d}"
            
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
                
                if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
                    logger.debug("No display detected, configuring for headless environment")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--disable-software-rasterizer")
                
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
                
                self.driver.set_page_load_timeout(60)
                self.driver.set_script_timeout(60)
                
                logger.debug("Setting up WebDriverWait with 30 second timeout...")
                self.wait = WebDriverWait(self.driver, 30)
                
                return
                
            except WebDriverException as e:
                last_exception = e
                retry_count += 1
                logger.warning(f"WebDriver initialization failed (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if hasattr(self, 'driver') and self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
                    
                if retry_count < max_retries:
                    sleep_time = retry_delay * retry_count
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to initialize WebDriver after {max_retries} attempts")
                    raise last_exception
        
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
            # Don't send notification here - it will be sent by the run method
            # after this function completes successfully

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
            self.send_notification(error_msg, priority="high", tags=["time", "error"], force=True)
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
                # No notification sent for no-op operations
                return False
            elif not should_clock_in and not is_clocked_in:
                msg = "Already clocked out"
                logger.info(msg)
                # No notification sent for no-op operations  
                return False

            action_name = "Clock In" if should_clock_in else "Clock Out"
            logger.info(f"Performing {action_name}")
            
            if should_clock_in:
                ActionChains(self.driver).move_to_element(clock_in_button).click().perform()
                # Get the latest time info for the notification
                time_info = self.get_time_info()
                # Send notification after successful completion
                notification_msg = (
                    f"Successfully clocked in\n"
                    f"Time worked today: {time_info.get('time_worked', 'N/A')}\n"
                    f"Time left: {time_info.get('time_left', 'N/A')}"
                )
                self.send_notification(notification_msg, tags=["clock", "in"])
            else:
                ActionChains(self.driver).move_to_element(clock_out_button).click().perform()
                # Get the latest time info for the notification
                time_info = self.get_time_info()
                # Send notification after successful completion
                notification_msg = (
                    f"Successfully clocked out\n"
                    f"Total time worked today: {time_info.get('time_worked', 'N/A')}"
                )
                self.send_notification(notification_msg, tags=["clock", "out"])
                
            return True

        except Exception as e:
            error_msg = f"Error handling time tracking: {str(e)}"
            logger.error(error_msg)
            self.send_notification(error_msg, priority="high", tags=["clock", "error"], force=True)
            raise

    def run(self):
        """Run status check"""
        try:
            self.setup_driver()
            self.login()
            # Store time info WITHOUT sending notification
            time_info = self.get_time_info()
            # Only return the info - let caller decide if notification is needed
            return time_info
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg)
            self.send_notification(error_msg, priority="high", tags=["time", "error"], force=True)
            raise
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser session closed")
        
    def run_clock_action(self, action='switch'):
        """Run clock in/out action"""
        try:
            self.setup_driver()
            self.login()
            action_performed = self.handle_time_tracking(action)
            if action_performed:
                logger.info("Time tracking operation completed successfully")
                # Notification already sent by handle_time_tracking on success
            else:
                logger.info("No action needed")
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg)
            self.send_notification(error_msg, priority="high", tags=["clock", "error"], force=True)
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

def parse_arguments():
    """Parse command line arguments"""
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
    parser.add_argument('--action', dest='explicit_action',
                        choices=['in', 'out', 'switch', 'status', 'auto-out'],
                        help='Specify action: "in" to clock in, "out" to clock out, "switch" to toggle, "status" to check, "auto-out" for auto clock-out')

    custom_args = sys.argv[1:]
    i = 0
    delay_params = []
    
    while i < len(custom_args):
        if custom_args[i] in ['-r', '--random-delay']:
            if i+1 >= len(custom_args) or custom_args[i+1].startswith('-') or custom_args[i+1] in ['in', 'out', 'switch', 'status', 'auto-out']:
                pass
            else:
                for j in range(1, 3):
                    if i+j < len(custom_args) and not custom_args[i+j].startswith('-') and custom_args[i+j] not in ['in', 'out', 'switch', 'status', 'auto-out']:
                        try:
                            float(custom_args[i+j])
                            delay_params.append(custom_args[i+j])
                        except ValueError:
                            break
                    else:
                        break
        i += 1
    
    known_args, remaining = parser.parse_known_args()
    
    action = None
    valid_actions = ['in', 'out', 'switch', 'status', 'auto-out']
    clean_remaining = []
    
    for arg in remaining:
        if arg in valid_actions:
            action = arg
        elif not (arg in delay_params):
            clean_remaining.append(arg)
    
    if known_args.explicit_action:
        action = known_args.explicit_action
    elif action is None:
        action = 'status'
    
    if clean_remaining:
        parser.error(f"Unrecognized arguments: {' '.join(clean_remaining)}")
    
    args = known_args
    args.action = action
    
    if known_args.random_delay is not None and not delay_params:
        args.random_delay = []
    
    return args

def process_random_delay(args):
    """Process random delay parameters"""
    if args.random_delay is None:
        return None
        
    if len(args.random_delay) == 0:
        return (0, 5)
    elif len(args.random_delay) == 1:
        try:
            min_delay = float(args.random_delay[0])
            return (min_delay, min_delay + 5)
        except ValueError:
            raise argparse.ArgumentTypeError("--random-delay values must be numbers")
    else:
        try:
            min_delay, max_delay = map(float, args.random_delay[:2])
            return (min_delay, max_delay)
        except ValueError:
            raise argparse.ArgumentTypeError("--random-delay values must be numbers")

def main(args=None):
    """Main execution function"""
    if args is None:
        args = parse_arguments()

    command = f"Command executed: {sys.executable} {' '.join(sys.argv)}"
    setup_logging(args.verbose)
    logger.info(command)
    load_environment(args.env_file)
    
    random_delay = process_random_delay(args)
    if random_delay:
        min_delay, max_delay = random_delay
        delay_secs = random.uniform(min_delay * 60, max_delay * 60)
        if not args.quiet:
            logger.info(f"Waiting {delay_secs/60:.2f} minutes...")
        try:
            time.sleep(delay_secs)
        except KeyboardInterrupt:
            handle_interrupt(None)
    
    automation = None
    try:
        if args.action == 'status':
            automation = TimeCheckAutomation(quiet=args.quiet or not args.ntfy)
            signal.signal(signal.SIGINT, lambda signum, frame: handle_interrupt(automation))
            time_info = automation.run()
            # Only send notification for explicit status check if notifications are enabled
            if automation.ntfy_topic and args.ntfy:
                status_message = (
                    f"Status check completed successfully\n"
                    f"Current status: {time_info['status']}\n" 
                    f"Time worked: {time_info.get('time_worked', 'N/A')}\n"
                    f"Time left: {time_info.get('time_left', 'N/A')}"
                )
                automation.send_notification(status_message, tags=["time", "check"])
            print(json.dumps(time_info, indent=2), file=sys.stdout)
        elif args.action == 'auto-out':
            # Handle auto-out case differently to prevent browser session closure
            automation = TimeCheckAutomation(quiet=args.quiet or not args.ntfy)
            signal.signal(signal.SIGINT, lambda signum, frame: handle_interrupt(automation))
            try:
                automation.setup_driver()
                automation.login()
                time_info = automation.get_time_info()
                
                if time_info.get('time_left') == "00:00:00" and time_info.get('status') != "Clocked Out":
                    # Use the same browser session to perform the clock out
                    action_performed = automation.handle_time_tracking("out")
                    if action_performed:
                        logger.info("Auto clock-out completed successfully")
                        # handle_time_tracking already sends notification on success
                else:
                    logger.info("Auto-out not needed: either already clocked out or time remaining")
                    # No notification when no action taken
            finally:
                if automation and automation.driver:
                    automation.driver.quit()
                    logger.info("Browser session closed")
        else:
            automation = TimeCheckAutomation(quiet=args.quiet or not args.ntfy)
            signal.signal(signal.SIGINT, lambda signum, frame: handle_interrupt(automation))
            automation.run_clock_action(args.action)
    except KeyboardInterrupt:
        handle_interrupt(automation)
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        if automation:
            automation.cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()
