# ttclock - Time Tracking Automation

This script automates clocking in and out on a web-based time-tracking system using Selenium and ntfy.sh notifications.

## Features

 - Automated login via environment variables
 - Handles clock-in and clock-out logic
 - Sends notifications via ntfy.sh
 - Uses Selenium WebDriver (Chrome)

## Installation

1. Install uv (if not already installed)
```
pip install uv || curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone the Repository
```
git clone https://github.com/nagazul/ttclock.git
cd ttclock
```
3. Set Up the Virtual Environment
```
uv venv .venv
```
4. Install Dependencies
```
# If using requirements.txt:
uv pip install -r requirements.txt

# Or, if using uv.lock:
uv sync
```

5. Copy and Modify .env File
```
cp .env.example .env
nvim .env
```

6. Run the Script
```
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

## Notes

 - Chrome and ChromeDriver are required. The script will attempt to download ChromeDriver automatically.
 - Ensure your environment variables are set properly in the .env file.
 - Uses ntfy.sh for notifications (optional but recommended).
