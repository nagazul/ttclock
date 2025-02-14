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
        self.driver = None
        self.wait = None

    def setup_driver(self):
        """Configure and initialize the Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--incognito")
        
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

    def handle_time_tracking(self):
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

            if clock_in_button.get_attribute("disabled"):
                logger.info("Performing Clock Out")
                ActionChains(self.driver).move_to_element(clock_out_button).click().perform()
            else:
                logger.info("Performing Clock In")
                ActionChains(self.driver).move_to_element(clock_in_button).click().perform()

        except TimeoutException as e:
            logger.error(f"Timeout while handling time tracking: {str(e)}")
            raise
        except WebDriverException as e:
            logger.error(f"WebDriver error during time tracking: {str(e)}")
            raise

    def run(self):
        """Main execution method"""
        try:
            self.setup_driver()
            self.login()
            self.handle_time_tracking()
            logger.info("Time tracking operation completed successfully")
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            raise
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser session closed")

if __name__ == "__main__":
    try:
        automation = TimeTrackingAutomation()
        automation.run()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        exit(1)
