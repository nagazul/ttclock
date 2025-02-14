from selenium import webdriveZZZZZZZselenium.webdriver.chrome.options import Options  # Correct options for Chrome
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Define the URL and user-agent
url = 'https://rotimetracking.emeal.XXXXXXX.com:4431/time/clockin'
user_agent = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/117.0'

# Create an Options object and configure it for Chrome
chrome_options = Options()
chrome_options.add_argument(f"user-agent={user_agent}")  # Set the user-agent
chrome_options.add_argument("--disable-infobars")  # Disable the automation message
chrome_options.add_argument("--start-maximized")  # Start Chrome maximized
chrome_options.add_argument("--incognito")  # Start in incognito mode
# chrome_options.add_argument('--headless')  # Uncomment this line if you want to run in headless mode

driver = webdriver.Chrome(options=chrome_options)

try:
    driver.set_window_size(1920, 1080)

    print("Opening URL...")
    driver.get(url)

    wait = WebDriverWait(driver, 200)
    username = wait.until(EC.presence_of_element_located((By.NAME, 'loginfmt')))

    print("Entering username...")
    username.send_keys('XXX@emeal.XXXXXXX.com')

    print("Submitting...")
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="idSIButton9"]'))).click()

    print("Entering password...")
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="passwordInput"]'))).send_keys('XXXXXXX')

    print("Submitting...")
    wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="submitButton"]'))).click()

    print("Confirm stay signed in...")
    wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="idSIButton9"]'))).click()

    print("Looking for clock in/out buttons...")
    clock_in_button = wait.until(
        EC.presence_of_element_located((By.XPATH, '/html/body/app-root/div/div/div/app-clockin/div[2]/div/div/app-clock/div/div[1]/div[2]/button[1]'))  # Replace with the actual ID
    )
    clock_out_button = wait.until(
        EC.presence_of_element_located((By.XPATH, '/html/body/app-root/div/div/div/app-clockin/div[2]/div/div/app-clock/div/div[1]/div[2]/button[2]'))  # Replace with the actual ID
    )
    print("Clock buttons found.")

    if clock_in_button.get_attribute("disabled"):
        print("Clicking Clock Out")
        action = ActionChains(driver)
        action.move_to_element(clock_out_button).click().perform()
    else:
        print("Clicking Clock In")
        action = ActionChains(driver)
        action.move_to_element(clock_in_button).click().perform()

finally:
    # Close the browser after execution
    driver.quit()

print("Done.")

