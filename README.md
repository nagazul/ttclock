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
# Basic Usage
uv run time.py                    # Check status (default action) in quiet mode
uv run time.py status             # Explicit status check
uv run time.py in                 # Clock in
uv run time.py out                # Clock out
uv run time.py switch             # Toggle current status (in->out or out->in)
uv run time.py auto-out           # Clock out only if time_left is 00:00:00

# Notification Options
uv run time.py -n                 # Enable notifications
uv run time.py -q                 # Force quiet mode (overrides -n)
uv run time.py status -n          # Status check with notifications
uv run time.py in -n              # Clock in with notifications

# Random Delay Options (-r)
uv run time.py -r                 # Default random delay (0-5 minutes)
uv run time.py -r 2               # Random delay between 2-7 minutes
uv run time.py -r 1 5             # Random delay between 1-5 minutes
uv run time.py switch -r 1 3      # Switch with 1-3 minute random delay

# Probability Options (-p)
uv run time.py -p 75              # 75% chance of executing
uv run time.py -p                 # Random probability (0-100%)
uv run time.py -p 50 in           # 50% chance of clocking in
uv run time.py -p 30 -r out       # 30% chance of clocking out with random delay

# Combined Examples
uv run time.py -p 80 -r 1 3 -n in # 80% chance of clock-in with 1-3 min delay and notifications
uv run time.py -p -r switch       # Random chance and random delay for status switch

# Output Formatting
uv run time.py | jq               # Format full JSON output
uv run time.py | jq -r '.time_worked' # Extract only time worked today

# Other Options
uv run time.py --env-file .env    # Use custom .env file
uv run time.py -v                 # Basic verbose logging
uv run time.py -vv                # Detailed logging
uv run time.py -vvv               # Full debug logging
```

## Cron
ttcron.sh logs in ~/.log/ttcron.log  
Multiple clock in times to catch one if your laptop is down...  
Multiple clock out times to make sure you clock out when the working time is over.    
ntfy only notifies when the status changes.  

### ttcron.sh Options

ttcron.sh supports these additional options:

- `-r`, `--random-delay`: Adds a random delay before execution
  - `-r min max`: Random delay between min-max minutes (e.g., `-r 1 5`)
  - `-r min`: Random delay between min and min+5 minutes
  - `-r`: Default random delay between 0-5 minutes

- `-p`, `--probability`, `--prob`: Controls probability of execution
  - `-p 75`: 75% chance of running the command
  - `-p` (no value): Uses a random probability between 0-100%

```bash
# Example cron entries:
15,45 06-07 * * 1-5 /home/.../ttclock/ttcron.sh -r --ntfy in        # Clock in with random delay
10,15 13 * * 1-5 /home/.../ttclock/ttcron.sh -p 75 out              # 75% chance to clock out at lunchtime
25,30 14 * * 1-5 /home/.../ttclock/ttcron.sh -p -r in               # Random chance with random delay
0,30 16-17 * * 1-5 /home/.../ttclock/ttcron.sh -r --ntfy auto-out   # Clock out with random delay
```

## Notes

 - Chrome and ChromeDriver are required. The script will attempt to download ChromeDriver automatically.
 - Ensure your environment variables are set properly in the .env file.
 - Uses ntfy.sh for notifications (optional but recommended).
