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
uv run python time.py                 # Default action is 'status'
uv run python time.py status -q | jq  # Check status explicitly (!ntfy)
uv run python time.py in              # Force clock-in
uv run python time.py out             # Force clock-out
uv run python time.py switch          # Switch in/out
python time.py -q                     # any command with notifications disabled
```

## Notes

 - Chrome and ChromeDriver are required. The script will attempt to download ChromeDriver automatically.
 - Ensure your environment variables are set properly in the .env file.
 - Uses ntfy.sh for notifications (optional but recommended).
