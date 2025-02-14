import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import logging
from dotenv import load_dotenv
import requests
from datetime import datetime

# Configure logging
def setup_logging(verbosity=0):
    # Configure root logger to stderr
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)  # Default to ERROR for root logger
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(handler)
    
    # Configure our script's logger
    script_logger = logging.getLogger(__name__)
    
    if verbosity == 0:  # Silent mode
        script_logger.setLevel(logging.ERROR)
        logging.getLogger('selenium').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.ERROR)
        logging.getLogger('WDM').setLevel(logging.ERROR)
    elif verbosity == 1:  # -v: Basic script messages
        script_logger.setLevel(logging.INFO)
        logging.getLogger('selenium').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.ERROR)
        logging.getLogger('WDM').setLevel(logging.ERROR)
    elif verbosity == 2:  # -vv: More detailed messages
        script_logger.setLevel(logging.DEBUG)
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('WDM').setLevel(logging.INFO)
    else:  # -vvv: All debug messages
        script_logger.setLevel(logging.DEBUG)
        logging.getLogger('selenium').setLevel(logging.DEBUG)
        logging.getLogger('urllib3').setLevel(logging.DEBUG)
        logging.getLogger('WDM').setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class TimeCheckAutomation:
    def __init__(self, quiet=False):
        self.url = os.getenv('TIMETRACKING_URL')
        self.username = os.getenv('TIMETRACKING_USERNAME')
        self.password = os.getenv('TIMETRACKING_PASSWORD')
        self.ntfy_topic = '' if quiet else os.getenv('NTFY_TOPIC', '')
        self.driver = None
        self.wait = None

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

    def setup_driver(self):
        """Configure and initialize the Chrome WebDriver"""
        logger.debug("Setting up Chrome options...")
        chrome_options = Options()
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--incognito")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        logger.debug("Checking for Chrome binary locations...")
        # Check common Chrome binary locations
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
        else:
            logger.warning("Could not find Chrome binary in common locations")
        
        logger.debug("Setting up ChromeDriver service...")
        service = Service(ChromeDriverManager().install())
        
        logger.debug("Initializing Chrome WebDriver...")
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.set_window_size(1920, 1080)
        logger.debug("Setting up WebDriverWait with 30 second timeout...")
        self.wait = WebDriverWait(self.driver, 30)

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
            
            # Wait for the app to fully load
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
            
            # Get all rows with time data
            rows = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.clocking-info tr"))
            )
            
            times = {}
            # Extract information from each row
            for row in rows:
                label = row.find_element(By.CLASS_NAME, "td-cell").text.strip()
                value = row.find_element(By.CLASS_NAME, "td-data").text.strip()
                
                # Convert date format if this is the date field
                if label == "Current Date":
                    # Convert from DD/MM/YYYY to YYYY-MM-DD
                    day, month, year = value.split('/')
                    value = f"{year}-{month}-{day}"
                
                times[label] = value
            
            # Get clock status
            clock_buttons = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "app-clock button"))
            )
            
            if len(clock_buttons) < 2:
                raise ValueError("Could not find clock buttons")

            clock_in_button = clock_buttons[0]
            is_clocked_in = clock_in_button.get_attribute("disabled") is not None
            status = "Clocked In" if is_clocked_in else "Clocked Out"
            
            # Prepare message with all information
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
            
            # Using more reliable selectors
            clock_buttons = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "app-clock button"))
            )
            
            if len(clock_buttons) < 2:
                raise ValueError("Could not find both clock in and clock out buttons")

            clock_in_button = clock_buttons[0]
            clock_out_button = clock_buttons[1]

            # Check current state
            is_clocked_in = clock_in_button.get_attribute("disabled") is not None
            
            # Determine action based on input and current state
            should_clock_in = {
                'in': True,
                'out': False,
                'switch': not is_clocked_in
            }.get(action)
            
            # If we're already in the desired state, log and return
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
            
            # Perform the action
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

    def run_clock_action(self, action='switch'):
        """Run clock in/out action"""
        try:
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

if __name__ == "__main__":
    import json
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Time tracking automation')
    parser.add_argument('action', nargs='?', choices=['in', 'out', 'switch', 'status'], 
                       default='status',
                       help='Specify action: "in" to clock in, "out" to clock out, '
                            '"switch" to toggle, "status" to check (default)')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Disable ntfy notifications')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                       help='Increase verbosity (can be used twice: -v or -vv)')
    
    args = parser.parse_args()
    
    # Setup logging based on verbosity level
    setup_logging(args.verbose)
    
    try:
        automation = TimeCheckAutomation(quiet=args.quiet)
        
        if args.action == 'status':
            time_info = automation.run()
            # Send only the JSON to stdout
            print(json.dumps(time_info, indent=2), file=sys.stdout)
        else:
            automation.run_clock_action(args.action)
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        exit(1)
