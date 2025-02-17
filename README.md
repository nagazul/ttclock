# ttclock - Time Tracking Automation

This script automates clocking in and out on a web-based time-tracking system using Selenium and ntfy.sh notifications.

## Features

 - Automated login via environment variables
 - Handles clock-in and clock-out logic
 - Sends notifications via ntfy.sh
 - Uses Selenium WebDriver (Chrome)

## Dependencies

- Google Chrome or Chromium browser
- uv package manager
- jq (optional, for JSON processing)
- ntfy.sh account (optional, for notifications)

### Installing Dependencies

1. Install uv package manager (if not already installed):
```bash
pip install uv || curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install Chrome/Chromium browser:
```bash
# Ubuntu
sudo apt install wget curl
curl -fSsL https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install google-chrome-stable

# macOS
brew install --cask google-chrome
```

3. Install jq (optional, for JSON processing):
```bash
# Ubuntu
sudo apt install jq

# macOS
brew install jq
```

## Installation

1. Clone the Repository:
```bash
git clone https://github.com/nagazul/ttclock.git
cd ttclock
```

2. Set Up the Virtual Environment:
```bash
uv venv .venv
```

3. Install Python Dependencies:
```bash
# If using requirements.txt:
uv pip install -r requirements.txt

# Or, if using uv.lock:
uv sync
```

4. Configure Environment:
```bash
cp .env.example .env
nvim .env
```

## Usage

```bash
uv run time.py                    # Default action is 'status' (quiet)
uv run time.py status | jq        # Check status and format JSON output
uv run time.py status -n          # Check status with ntfy notifications
uv run time.py in                 # Force clock-in (quiet)
uv run time.py in -n              # Force clock-in with notifications
uv run time.py out                # Force clock-out (quiet)
uv run time.py auto-out           # Clock-out only if time_left is 00:00:00 
uv run time.py switch             # Switch in/out (quiet)
uv run time.py -q                 # Force quiet mode (overrides -n)

uv run time.py switch -r 1 5      # Random delay between 1-5 minutes before switch

# Verbosity levels (can be combined with any command):
uv run time.py -v                 # Basic operational messages
uv run time.py -vv                # Detailed operation messages
uv run time.py -vvv               # Full debug output

# Get the time clocked today
uv run time.py | jq -r '.time_worked'

# Notification examples:
uv run time.py status -n          # Status check with notifications
uv run time.py switch -n -r 1 5   # Switch with notifications and random delay
uv run time.py -n -q              # -q overrides -n, runs in quiet mode
```

## Cron

```
50 07 * * 1-5 /home/.../ttclock/ttcron.sh in          # Clock in
10 13 * * 1-5 /home/.../ttclock/ttcron.sh out         # nap
00 14 * * 1-5 /home/.../ttclock/ttcron.sh in
0,30 16-17 * * 1-5 /home/.../ttclock/ttcron.sh auto   # Clock out
```

## Notes

 - Chrome and ChromeDriver are required. The script will attempt to download ChromeDriver automatically.
 - Ensure your environment variables are set properly in the .env file.
 - Uses ntfy.sh for notifications (optional but recommended).
