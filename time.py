import os
import requests
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
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class TimeTrackingAutomation:
    def __init__(self):
        self.url = os.getenv('TIMETRACKING_URL')
        self.username = os.getenv('TIMETRACKING_USERNAME')
        self.password = os.getenv('TIMETRACKING_PASSWORD')
        self.ntfy_topic = os.getenv('NTFY_TOPIC', '')  # Default to empty string
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
                "Tags": ','.join(tags) if tags else "clock"
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
        chrome_options = Options()
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--incognito")
        chrome_options.add_argument("--headless=new")  # Modern headless mode
        chrome_options.add_argument("--disable-gpu")   # Recommended for headless
        chrome_options.add_argument("--no-sandbox")    # Required for some Linux systems
        chrome_options.add_argument("--disable-dev-shm-usage")  # Prevent memory issues
        
        # Check common Chrome binary locations
        chrome_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser'
        ]
        
        chrome_binary = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_binary = path
                break
                
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info(f"Using Chrome binary at: {chrome_binary}")
        else:
            logger.warning("Could not find Chrome binary in common locations")
        
        # Optional headless mode
        if os.getenv('HEADLESS_MODE', 'false').lower() == 'true':
            chrome_options.add_argument('--headless')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.set_window_size(1920, 1080)
        self.wait = WebDriverWait(self.driver, 30)  # Reduced wait time from 200

    def login(self):
        """Handle the login process"""
        try:
            logger.info("Navigating to login page...")
            self.driver.get(self.url)

            # Enter username
            username_field = self.wait.until(EC.presence_of_element_located((By.NAME, 'loginfmt')))
            username_field.send_keys(self.username)
            self.wait.until(EC.element_to_be_clickable((By.ID, 'idSIButton9'))).click()

            # Enter password
            password_field = self.wait.until(EC.presence_of_element_located((By.ID, 'passwordInput')))
            password_field.send_keys(self.password)
            self.wait.until(EC.element_to_be_clickable((By.ID, 'submitButton'))).click()

            # Handle "Stay signed in" prompt
            self.wait.until(EC.element_to_be_clickable((By.ID, 'idSIButton9'))).click()
            logger.info("Login successful")

        except TimeoutException as e:
            logger.error(f"Timeout during login process: {str(e)}")
            raise
        except WebDriverException as e:
            logger.error(f"WebDriver error during login: {str(e)}")
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
            is_clocked_in = clock_in_button.get_attribute("disabled")
            
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

        except TimeoutException as e:
            logger.error(f"Timeout while handling time tracking: {str(e)}")
            raise
        except WebDriverException as e:
            logger.error(f"WebDriver error during time tracking: {str(e)}")
            raise

    def run(self, action='switch'):
        """Main execution method"""
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
    import argparse
    
    parser = argparse.ArgumentParser(description='Time tracking automation')
    parser.add_argument('action', nargs='?', choices=['in', 'out', 'switch'], 
                       default='switch',
                       help='Specify action: "in" to clock in, "out" to clock out, "switch" to toggle (default)')
    
    args = parser.parse_args()
    
    try:
        automation = TimeTrackingAutomation()
        automation.run(action=args.action)
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        exit(1)
