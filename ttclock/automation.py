import os
import sys
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from .utils import send_notification, capture_screenshot


class TimeCheckAutomation:
    def __init__(self, quiet=True):
        self.url = os.getenv('TIMETRACKING_URL')
        self.username = os.getenv('TIMETRACKING_USERNAME')
        self.password = os.getenv('TIMETRACKING_PASSWORD')
        self.ntfy_topic = os.getenv('NTFY_TOPIC', '') if not quiet else ''
        self.browser = None
        self.page = None
        self.playwright = None
        # Flag to control if notifications are sent (affected by -q and -n)
        self.notifications_enabled = not quiet and bool(self.ntfy_topic)
        # Initialize logger
        import logging
        self.logger = logging.getLogger('ttclock')
        self.logger.debug(f"Notifications enabled: {self.notifications_enabled} (quiet={quiet}, ntfy_topic='{self.ntfy_topic}')")

        if not self.url or not self.username or not self.password:
            self.logger.error("Missing required environment variables: TIMETRACKING_URL, TIMETRACKING_USERNAME, TIMETRACKING_PASSWORD")
            sys.exit(1)

    def cleanup(self):
        """Cleanup resources"""
        if self.browser:
            try:
                self.logger.info("Cleaning up browser session...")
                self.browser.close()
                self.browser = None
                if self.playwright:
                    self.playwright.stop()
                    self.playwright = None
            except Exception as e:
                self.logger.error(f"Error during browser cleanup: {str(e)}")

    def setup_driver(self, max_retries=3, retry_delay=5):
        """Configure and initialize the Playwright browser with retry mechanism"""
        retry_count = 0
        last_exception = None

        while retry_count < max_retries:
            try:
                self.logger.debug(f"Setting up Playwright browser (attempt {retry_count + 1}/{max_retries})...")
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(
                    headless=True,
                    channel="chrome",
                    args=[
                        "--disable-infobars",
                        "--no-sandbox",
                        "--disable-extensions",
                        "--dns-prefetch-disable",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--window-size=1920,1080",
                        "--disable-background-timer-throttling",
                        "--disable-renderer-backgrounding",
                        "--disable-backgrounding-occluded-windows"
                    ]
                )
                self.page = self.browser.new_page()

                # Set default timeout for actions
                self.page.set_default_timeout(30000)  # 30 seconds

                self.logger.info("Playwright browser setup successful.")
                return  # Exit the loop on success

            except PlaywrightError as e:
                last_exception = e
                retry_count += 1
                self.logger.warning(f"Playwright initialization failed (attempt {retry_count}/{max_retries}): {str(e)}")

                # Clean up any partially created browser instance
                if hasattr(self, 'browser') and self.browser:
                    try:
                        self.browser.close()
                    except: pass  # Ignore errors during cleanup
                    self.browser = None
                if hasattr(self, 'playwright') and self.playwright:
                    try:
                        self.playwright.stop()
                    except: pass
                    self.playwright = None

                if retry_count < max_retries:
                    sleep_time = retry_delay * (2**(retry_count - 1))  # Exponential backoff
                    self.logger.info(f"Retrying browser setup in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    self.logger.error(f"Failed to initialize browser after {max_retries} attempts.")
                    # Send a critical notification if setup fails completely
                    send_notification(f"Critical Error: Failed to initialize browser after {max_retries} attempts. Last error: {str(last_exception)}", priority="high", tags=["setup", "error"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
                    raise last_exception  # Re-raise the last exception
            except Exception as e:
                # Catch other potential errors during setup
                self.logger.error(f"An unexpected error occurred during browser setup: {str(e)}")
                send_notification(f"Critical Error: Unexpected error during browser setup: {str(e)}", priority="high", tags=["setup", "error"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
                raise  # Re-raise the exception

        # This part should ideally not be reached if the loop logic is correct
        self.logger.critical("Exited browser setup loop unexpectedly.")
        raise RuntimeError("Unexpected exit from browser setup routine.")

    def login(self):
        """Handle the login process"""
        if not self.page:
            self.logger.error("Browser not initialized before calling login.")
            raise RuntimeError("Browser not initialized.")
        try:
            self.logger.info(f"Navigating to login page: {self.url}")
            self.page.goto(self.url)
            self.logger.debug(f"Current URL after navigation: {self.page.url}")

            # --- Microsoft Login Flow ---
            # 1. Enter username
            self.logger.debug("Waiting for username field (loginfmt)...")
            self.page.wait_for_selector('input[name="loginfmt"]', timeout=30000)
            self.logger.debug("Entering username...")
            self.page.fill('input[name="loginfmt"]', self.username)

            # 2. Click Next
            self.logger.debug("Waiting for Next button (idSIButton9)...")
            self.page.wait_for_selector('#idSIButton9', state='visible', timeout=30000)
            self.logger.debug("Clicking Next button...")
            self.page.click('#idSIButton9')

            # 3. Enter password
            self.logger.debug("Waiting for password field (passwordInput)...")
            self.page.wait_for_selector('#passwordInput', state='visible', timeout=30000)
            self.logger.debug("Entering password...")
            self.page.fill('#passwordInput', self.password)

            # 4. Click Submit (Sign in)
            self.logger.debug("Waiting for Submit button (submitButton)...")
            self.page.wait_for_selector('#submitButton', state='visible', timeout=30000)
            self.logger.debug("Clicking Submit button...")
            self.page.click('#submitButton')

            # 5. Handle 'Stay signed in?' prompt
            self.logger.debug("Waiting for 'Stay signed in?' prompt (idSIButton9)...")
            try:
                # This prompt might not always appear, use a shorter timeout
                self.page.wait_for_selector('#idSIButton9', state='visible', timeout=10000)
                self.logger.debug("Handling 'Stay signed in?' prompt by clicking Yes...")
                self.page.click('#idSIButton9')
            except PlaywrightTimeoutError:
                self.logger.debug("'Stay signed in?' prompt not detected or timed out, continuing...")

            # --- Wait for Application Load ---
            self.logger.debug("Waiting for main application elements (app-root and app-clock)...")
            # Wait for a reliable element indicating the app has loaded
            self.page.wait_for_selector('app-root', timeout=30000)
            self.page.wait_for_selector('app-clock', timeout=30000)

            self.logger.info("Login successful and application appears loaded.")
            self.logger.debug(f"Final URL after login: {self.page.url}")

        except PlaywrightTimeoutError as e:
            page_title = self.page.title if self.page else "N/A"
            current_url = self.page.url if self.page else "N/A"
            error_msg = f"Timeout during login process at URL {current_url} (Title: {page_title}). Element not found: {str(e)}"
            self.logger.error(error_msg)
            # Try to capture screenshot on timeout
            capture_screenshot(self.page, "login_timeout_error")
            self.logger.debug(f"Page content at timeout (first 1000 chars): {self.page.content()[:1000]}...")
            send_notification(f"Login Error: Timeout - {str(e)}", priority="high", tags=["login", "error", "timeout"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise PlaywrightTimeoutError(error_msg) from e  # Re-raise with more context
        except PlaywrightError as e:
            self.logger.error(f"Playwright error during login: {str(e)}")
            capture_screenshot(self.page, "login_playwright_error")
            send_notification(f"Login Error: PlaywrightError - {str(e)}", priority="high", tags=["login", "error", "playwright"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise  # Re-raise the original exception
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during login: {str(e)}")
            capture_screenshot(self.page, "login_unexpected_error")
            send_notification(f"Login Error: Unexpected - {str(e)}", priority="high", tags=["login", "error", "unexpected"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise  # Re-raise the original exception

    def remove_blocking_modal(self):
        """Checks for and removes the specific blocking modal using JavaScript."""
        if not self.page:
            self.logger.warning("Attempted to remove modal, but page is not initialized.")
            return

        self.logger.debug("Checking for blocking modal...")
        script = """
() => {
    var modals = document.querySelectorAll('[class*="modal"]');
    var disabled = 0;
    modals.forEach(modal => {
        modal.style.display = 'none';
        console.log('Disabled modal:', modal.className);
        disabled++;
    });
    // Also try to remove specific known blockers
    var backdrop = document.querySelector('div.modal-backdrop');
    var container = document.querySelector('div.modal-container');
    if (backdrop) {
        backdrop.remove();
        console.log('Removed modal backdrop.');
        disabled++;
    }
    if (container) {
        container.remove();
        console.log('Removed modal container.');
        disabled++;
    }
    return disabled;
}
        """
        try:
            disabled = self.page.evaluate(script)
            if disabled:
                self.logger.info(f"Detected and disabled {disabled} blocking modal elements.")
            else:
                self.logger.debug("Blocking modal not found.")
        except PlaywrightError as e:
            self.logger.error(f"Playwright error while trying to remove modal: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error while removing modal: {str(e)}")

    def get_time_info(self):
        """Get the time information from the page"""
        if not self.page:
            self.logger.error("Browser not initialized before calling get_time_info.")
            raise RuntimeError("Browser not initialized.")
        try:
            self.logger.info("Attempting to retrieve time information...")

            # Remove any blocking modals before scraping
            self.remove_blocking_modal()

            # Wait for the table containing the info to be present
            self.logger.debug("Waiting for clocking info table...")
            self.page.wait_for_selector("table.clocking-info", timeout=30000)

            # Find all rows within the table body
            self.logger.debug("Locating rows in the table...")
            rows = self.page.query_selector_all("table.clocking-info tbody tr")
            if not rows:
                self.logger.warning("No rows found within the clocking info table body.")
                # Attempt to capture screenshot if table structure is unexpected
                capture_screenshot(self.page, "get_time_info_no_rows")
                # Return empty dict or raise error depending on desired behavior
                return {}  # Or raise ValueError("No data rows found in time info table")

            times = {}
            self.logger.debug(f"Processing {len(rows)} rows...")
            for i, row in enumerate(rows):
                try:
                    # Find label and value cells within the row
                    cells = row.query_selector_all("td")
                    if len(cells) >= 2:
                        label = cells[0].inner_text().strip()
                        value = cells[1].inner_text().strip()
                        self.logger.debug(f"Row {i}: Label='{label}', Value='{value}'")

                        # Standardize date format if found
                        if label == "Current Date" and value:
                            try:
                                # Assuming DD/MM/YYYY format
                                day, month, year = value.split('/')
                                value = f"{year}-{month}-{day}"  # Convert to YYYY-MM-DD
                            except ValueError:
                                self.logger.warning(f"Could not parse date '{value}' in expected DD/MM/YYYY format.")
                                # Keep original value if parsing fails

                        times[label] = value
                    else:
                        self.logger.warning(f"Row {i} does not have at least 2 cells (td elements). Skipping row.")

                except Exception as e:
                    self.logger.warning(f"Error processing row {i}: {str(e)}. Skipping row.")
                    continue  # Skip to the next row if an error occurs

            # Determine Clock In/Out Status
            self.logger.debug("Checking clock button status...")
            try:
                # Wait for the buttons to be present within app-clock
                self.page.wait_for_selector("app-clock", timeout=30000)
                clock_buttons = self.page.query_selector_all("app-clock button")

                if len(clock_buttons) >= 2:
                    clock_in_button = clock_buttons[0]
                    # Check if the clock-in button is disabled (means user is clocked in)
                    is_clocked_in = clock_in_button.get_attribute("disabled") is not None
                    status = "Clocked In" if is_clocked_in else "Clocked Out"
                    self.logger.debug(f"Determined status based on button state: {status}")
                else:
                    self.logger.warning(f"Expected at least 2 clock buttons, found {len(clock_buttons)}. Cannot determine status accurately.")
                    status = "Unknown"
                    capture_screenshot(self.page, "get_time_info_missing_buttons")

            except PlaywrightTimeoutError:
                self.logger.error("Timed out waiting for clock buttons to determine status.")
                status = "Unknown (Timeout)"
                capture_screenshot(self.page, "get_time_info_button_timeout")
            except Exception as e:
                self.logger.error(f"Error determining clock status from buttons: {str(e)}")
                status = "Unknown (Error)"
                capture_screenshot(self.page, "get_time_info_button_error")

            # Prepare result dictionary
            result = {
                'status': status,
                'first_clock': times.get('First clock in'),
                'time_worked': times.get('All for today'),  # Key based on user's script
                'time_left': times.get('Time left'),
                'date': times.get('Current Date')  # Already formatted to YYYY-MM-DD
            }

            # Log the retrieved information
            log_message = (
                f"Retrieved time info: Status='{result['status']}', "
                f"First Clock='{result['first_clock']}', Worked='{result['time_worked']}', "
                f"Left='{result['time_left']}', Date='{result['date']}'"
            )
            self.logger.info(log_message)

            # Return the dictionary - Notification is handled by the calling method (run or run_clock_action)
            return result

        except PlaywrightTimeoutError as e:
            error_msg = f"Timeout error while getting time info: {str(e)}"
            self.logger.error(error_msg)
            capture_screenshot(self.page, "get_time_info_timeout_error")
            send_notification(f"Error getting time info: Timeout - {str(e)}", priority="high", tags=["time", "error", "timeout"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise PlaywrightTimeoutError(error_msg) from e
        except PlaywrightError as e:
            error_msg = f"Could not find expected element while getting time info: {str(e)}"
            self.logger.error(error_msg)
            capture_screenshot(self.page, "get_time_info_no_element_error")
            send_notification(f"Error getting time info: Element not found - {str(e)}", priority="high", tags=["time", "error", "missing_element"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise PlaywrightError(error_msg) from e
        except Exception as e:
            error_msg = f"An unexpected error occurred getting time info: {str(e)}"
            self.logger.error(error_msg, exc_info=True)  # Log traceback for unexpected errors
            capture_screenshot(self.page, "get_time_info_unexpected_error")
            send_notification(f"Error getting time info: Unexpected - {str(e)}", priority="high", tags=["time", "error", "unexpected"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise  # Re-raise the original exception

    def handle_time_tracking(self, action='switch'):
        """Handle the clock in/out process based on the specified action."""
        if not self.page:
            self.logger.error("Browser not initialized before calling handle_time_tracking.")
            raise RuntimeError("Browser not initialized.")
        try:
            self.logger.info(f"Attempting to handle time tracking action: '{action}'")

            # --- Locate Clock Buttons ---
            self.logger.debug("Waiting for clock buttons within app-clock...")
            try:
                self.page.wait_for_selector("app-clock", timeout=30000)
                # Ensure buttons inside are interactable
                self.page.wait_for_selector("app-clock button", state='visible', timeout=30000)
                clock_buttons = self.page.query_selector_all("app-clock button")
            except PlaywrightTimeoutError as e:
                self.logger.error(f"Could not find or wait for clock buttons: {str(e)}")
                capture_screenshot(self.page, "handle_time_tracking_button_timeout")
                raise PlaywrightTimeoutError(f"Failed to find clock buttons: {str(e)}") from e

            if len(clock_buttons) < 2:
                self.logger.error(f"Expected at least 2 clock buttons, found {len(clock_buttons)}.")
                capture_screenshot(self.page, "handle_time_tracking_missing_buttons")
                raise ValueError(f"Could not find both clock buttons (found {len(clock_buttons)})")

            clock_in_button = clock_buttons[0]
            clock_out_button = clock_buttons[1]

            # --- Determine Current Status and Target Action ---
            is_clocked_in = clock_in_button.get_attribute("disabled") is not None
            current_status = "Clocked In" if is_clocked_in else "Clocked Out"
            self.logger.debug(f"Current status determined as: {current_status}")

            target_action = None  # 'clock_in', 'clock_out', or None (no action needed)
            if action == 'in':
                if not is_clocked_in:
                    target_action = 'clock_in'
                else:
                    self.logger.info("Action 'in' requested, but already clocked in. No action taken.")
            elif action == 'out':
                if is_clocked_in:
                    target_action = 'clock_out'
                else:
                    self.logger.info("Action 'out' requested, but already clocked out. No action taken.")
            elif action == 'switch':
                target_action = 'clock_out' if is_clocked_in else 'clock_in'
                self.logger.info(f"Action 'switch' requested. Will attempt to {target_action.replace('_', ' ')}.")
            else:
                self.logger.warning(f"Invalid action '{action}' passed to handle_time_tracking. No action taken.")
                return False  # Indicate no action was performed

            # --- Perform Action if Needed ---
            if target_action:
                button_to_click = clock_in_button if target_action == 'clock_in' else clock_out_button
                action_name = "Clock In" if target_action == 'clock_in' else "Clock Out"
                self.logger.info(f"Performing action: {action_name}")

                try:
                    # Remove any blocking modals before clicking
                    self.remove_blocking_modal()
                    # Click the button
                    self.logger.debug(f"Attempting to click {action_name} button...")
                    button_to_click.click()
                    self.logger.debug(f"{action_name} button clicked successfully.")

                    # Add a small delay to allow the UI to update after the click
                    time.sleep(1)  # Adjust as needed

                    # --- Verify Action and Send Notification ---
                    # Re-fetch time info to confirm the action and get updated times
                    self.logger.info("Fetching updated time info after action...")
                    time_info = self.get_time_info()  # This already has error handling

                    # Verify the status change (optional but good practice)
                    new_status = time_info.get('status', 'Unknown')
                    expected_status = "Clocked In" if target_action == 'clock_in' else "Clocked Out"
                    if new_status == expected_status:
                        self.logger.info(f"Action {action_name} confirmed. New status: {new_status}")
                    elif new_status == "Unknown":
                        self.logger.warning(f"Action {action_name} performed, but could not confirm new status.")
                    else:
                        self.logger.warning(f"Action {action_name} performed, but status is unexpectedly '{new_status}' (expected '{expected_status}').")
                        capture_screenshot(self.page, f"{target_action}_status_mismatch")

                    # Send notification based on the action performed
                    if target_action == 'clock_in':
                        notification_msg = (
                            f"Successfully clocked in.\n"
                            f"Time worked today: {time_info.get('time_worked', 'N/A')}\n"
                            f"Time left: {time_info.get('time_left', 'N/A')}"
                        )
                        send_notification(notification_msg, tags=["clock", "in", "success"], ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
                    else:  # clock_out
                        notification_msg = (
                            f"Successfully clocked out.\n"
                            f"Total time worked today: {time_info.get('time_worked', 'N/A')}"
                        )
                        send_notification(notification_msg, tags=["clock", "out", "success"], ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)

                    return True  # Indicate action was successfully performed

                except PlaywrightTimeoutError as e:
                    error_msg = f"Timeout while trying to click {action_name} button or waiting after click: {str(e)}"
                    self.logger.error(error_msg)
                    capture_screenshot(self.page, f"{target_action}_click_timeout")
                    send_notification(f"Error during {action_name}: Timeout - {str(e)}", priority="high", tags=["clock", "error", "timeout"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
                    raise PlaywrightTimeoutError(error_msg) from e
                except PlaywrightError as e:
                    # Catch potential issues like element not interactable
                    error_msg = f"Playwright error performing {action_name}: {str(e)}"
                    self.logger.error(error_msg)
                    capture_screenshot(self.page, f"{target_action}_click_playwright_error")
                    send_notification(f"Error during {action_name}: PlaywrightError - {str(e)}", priority="high", tags=["clock", "error", "playwright"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
                    raise  # Re-raise
                except Exception as e:
                    # Catch errors during the get_time_info call after action
                    error_msg = f"Error after performing {action_name} (likely during status update check): {str(e)}"
                    self.logger.error(error_msg, exc_info=True)
                    # Notification for the original error is likely already sent by get_time_info
                    # Optionally send another one indicating context
                    send_notification(f"Error after {action_name}: {str(e)}", priority="high", tags=["clock", "error", "post_action"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
                    raise  # Re-raise
            else:
                # Case where no action was needed (e.g., already clocked in when 'in' was requested)
                return False  # Indicate no action was performed

        except Exception as e:
            # Catch errors before the action is attempted (e.g., finding buttons)
            error_msg = f"An unexpected error occurred in handle_time_tracking before action '{action}': {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            capture_screenshot(self.page, "handle_time_tracking_unexpected_error")
            send_notification(f"Error handling time tracking ({action}): {str(e)}", priority="high", tags=["clock", "error", "unexpected"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise  # Re-raise

    def _prepare_browser(self):
        """Common browser preparation: setup, login, and modal removal."""
        self.setup_driver()
        self.login()
        self.remove_blocking_modal()

    def run_status_check(self):
        """Runs only the status check part of the automation."""
        try:
            self._prepare_browser()
            time_info = self.get_time_info() # Retrieve status

            # Send notification specifically for status check success if enabled
            if self.notifications_enabled:
                  status_message = (
                      f"Status check successful.\n"
                      f"Current status: {time_info.get('status', 'Unknown')}\n"
                      f"Time worked: {time_info.get('time_worked', 'N/A')}\n"
                      f"Time left: {time_info.get('time_left', 'N/A')}"
                  )
                  send_notification(status_message, tags=["time", "check", "success"], ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)

            return time_info # Return the dictionary containing time info
        except (PlaywrightTimeoutError, PlaywrightError, ValueError, RuntimeError) as e:
            # Errors during setup, login, or get_time_info are already logged and notified
            self.logger.error(f"Status check failed due to: {str(e)}")
            # No need to send another notification here, previous steps handle it.
            raise # Re-raise the exception
        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"An unexpected error occurred during status check: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            send_notification(error_msg, priority="high", tags=["time", "check", "error", "unexpected"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise
        finally:
            self.cleanup() # Ensure browser is closed

    def run_clock_action(self, action='switch'):
        """Runs the clock in/out action part of the automation."""
        try:
            self._prepare_browser()
            action_performed = self.handle_time_tracking(action)

            if action_performed:
                self.logger.info(f"Clock action '{action}' completed successfully.")
                # Notification is already sent by handle_time_tracking on success
            else:
                self.logger.info(f"Clock action '{action}' resulted in no operation (e.g., already in desired state).")
                # Optionally send a notification indicating no action was needed, if desired
                # self.send_notification(f"Clock action '{action}' not needed.", tags=["clock", "no_op"])

        except (PlaywrightTimeoutError, PlaywrightError, ValueError, RuntimeError) as e:
            # Errors during setup, login, or handle_time_tracking are logged and notified
            self.logger.error(f"Clock action '{action}' failed due to: {str(e)}")
            # No need to send another notification here.
            raise # Re-raise exception
        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"An unexpected error occurred during clock action '{action}': {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            send_notification(error_msg, priority="high", tags=["clock", "action", "error", "unexpected"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise
        finally:
            self.cleanup() # Ensure browser is closed

    def run_auto_out(self):
        """Checks status and clocks out automatically if time left is 00:00:00."""
        try:
            self._prepare_browser()

            self.logger.info("Running auto-out check...")
            time_info = self.get_time_info()

            status = time_info.get('status')
            time_left = time_info.get('time_left')

            self.logger.debug(f"Auto-out check: Status='{status}', Time Left='{time_left}'")

            if status == "Clocked In" and time_left == "00:00:00":
                self.logger.info("Conditions met for auto clock-out (Clocked In and Time Left is 00:00:00).")
                # Use the existing browser session to clock out
                action_performed = self.handle_time_tracking("out")
                if action_performed:
                    self.logger.info("Auto clock-out performed successfully.")
                    # Notification sent by handle_time_tracking
                else:
                    # This case should ideally not happen if status was correct, but log it.
                    self.logger.warning("Auto clock-out condition met, but handle_time_tracking reported no action was taken.")
            elif status == "Clocked Out":
                self.logger.info("Auto-out check: Already clocked out. No action needed.")
            elif status == "Clocked In":
                self.logger.info(f"Auto-out check: Still clocked in, but time left is '{time_left}'. No action needed.")
            else:
                  self.logger.warning(f"Auto-out check: Status is '{status}'. Cannot determine if auto-out is needed.")

        except (PlaywrightTimeoutError, PlaywrightError, ValueError, RuntimeError) as e:
            self.logger.error(f"Auto-out check failed due to: {str(e)}")
            # Error notifications handled in underlying methods
            raise
        except Exception as e:
            error_msg = f"An unexpected error occurred during auto-out check: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            send_notification(error_msg, priority="high", tags=["clock", "auto_out", "error", "unexpected"], force=True, ntfy_topic=self.ntfy_topic, notifications_enabled=self.notifications_enabled)
            raise
        finally:
            self.cleanup() # Ensure browser is closed