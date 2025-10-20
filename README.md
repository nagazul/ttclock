# ttclock - Time Tracking Automation

This script automates clocking in and out on a web-based time-tracking system using Playwright and ntfy.sh notifications.

## Features

 - Automated login via environment variables
 - Handles clock-in and clock-out logic
 - Sends notifications via ntfy.sh
 - Uses Playwright (Chrome/Chromium)
 - Cross-platform: Linux, macOS, Windows

## Dependencies

- Google Chrome or Chromium browser
- uv package manager (or pip)
- jq (optional, for JSON processing on Unix-like systems)
- ntfy.sh account (optional, for notifications)

### Installing Dependencies

1. Install uv package manager (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Install Chrome/Chromium browser:
```bash
# Ubuntu #1
sudo apt install wget curl
curl -fSsL https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install google-chrome-stable

# Ubuntu #2
sudo apt-get install -y wget unzip fonts-liberation libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libgbm1
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f -y

# macOS
brew install --cask google-chrome

# Windows
# Download and install Chrome from https://www.google.com/chrome/
# Or use winget: winget install Google.Chrome
```

3. Install jq (optional, for JSON processing):
```bash
# Ubuntu
sudo apt install jq

# macOS
brew install jq
```

## Installation

### Option 1: Local Development Setup

```bash
# Clone and navigate to repository
git clone https://github.com/nagazul/ttclock.git && cd ttclock

# Create virtual environment and install dependencies
uv venv && uv sync

# Configure environment
cp .ttclock.env.example ~/.ttclock.env
chmod 600 ~/.ttclock.env
```

### Option 2: User-Wide Installation

```bash
# Clone and build package
git clone https://github.com/nagazul/ttclock.git && cd ttclock
uv build

# Set up user environment and install
cd ~ && uv venv
uv pip install ~/ttclock/dist/ttclock-*.whl

# Add to PATH
echo 'export PATH="$HOME/.venv/bin:$PATH"' >> ~/.bash_aliases
source ~/.bash_aliases
```

With Option 2, you can run `ttclock` commands directly from anywhere without activating the environment.

### Windows Installation

```powershell
# Install uv (if not already installed)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone and navigate
git clone https://github.com/nagazul/ttclock.git
cd ttclock

# Create virtual environment and install
uv venv
uv sync

# Configure environment
# Copy .ttclock.env.example to %USERPROFILE%\.ttclock.env and edit
copy .ttclock.env.example %USERPROFILE%\.ttclock.env
# Edit the file with your credentials
notepad %USERPROFILE%\.ttclock.env
```

On Windows, run commands with `uv run ttclock` or activate the venv first.

## Usage

```bash
# Basic Usage
uv run ttclock                        # Check status (default action) in quiet mode
uv run ttclock status                 # Explicit status check
uv run ttclock in                     # Clock in
uv run ttclock out                    # Clock out
uv run ttclock switch                 # Toggle current status (in->out or out->in)
uv run ttclock auto-out               # Clock out only if time_left is 00:00:00

# Notification Options
uv run ttclock -n                     # Enable notifications
uv run ttclock -q                     # Force quiet mode (overrides -n)
uv run ttclock status -n              # Status check with notifications
uv run ttclock in -n                  # Clock in with notifications

# Random Delay Options (-r)
uv run ttclock -r                     # Default random delay (0-5 minutes)
uv run ttclock -r 2                   # Random delay between 2-7 minutes
uv run ttclock -r 1 5                 # Random delay between 1-5 minutes
uv run ttclock switch -r 1 3          # Switch with 1-3 minute random delay

# Probability Options (-p)
uv run ttclock -p 75                  # 75% chance of executing
uv run ttclock -p                     # Random probability (0-100%)
uv run ttclock -p 50 in               # 50% chance of clocking in
uv run ttclock -p 30 -r out           # 30% chance of clocking out with random delay

# Combined Examples
uv run ttclock -p 80 -r 1 3 -n in     # 80% chance of clock-in with 1-3 min delay and notifications
uv run ttclock -p -r switch           # Random chance and random delay for status switch

# Output Formatting
uv run ttclock | jq                   # Format full JSON output
uv run ttclock | jq -r '.time_worked' # Extract only time worked today

# Other Options
uv run ttclock --env-file .env        # Use custom .env file
uv run ttclock -v                     # Basic verbose logging
uv run ttclock -vv                    # Detailed logging
uv run ttclock -vvv                   # Full debug logging
```

## Scheduling
ttcron.sh logs in ~/.log/ttcron.log (Unix/Linux/macOS)  
Multiple clock in times to catch one if your laptop is down...  
Multiple clock out times to make sure you clock out when the working time is over.    
ntfy only notifies when the status changes.

### Windows Scheduling
Use Task Scheduler or create a batch file:

```batch
@echo off
uv run ttclock in
```

Schedule with Task Scheduler for daily execution.  

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
# Improved cron entries with wider time spreads and probability for human-like randomness:
15,45 6-7   * * 1-5  /home/.../ttclock/ttcron.sh -p 60 -r 1 15 --ntfy in           # 60% chance morning clock-in at varied times with 1-15 min delay
10,40 12-13 * * 1-5  /home/.../ttclock/ttcron.sh -p 70 -r out                      # 70% chance lunch clock-out with random delay
20,50 13-14 * * 1-5  /home/.../ttclock/ttcron.sh -p 75 -r 1 10 in                  # 75% chance afternoon clock-in with 1-10 min delay
0,30  16-18 * * 1-5  /home/.../ttclock/ttcron.sh -p 80 -r 1 10 --ntfy auto-out     # 80% chance evening auto-out with 1-10 min delay
```

## Notes

 - Chrome/Chromium is required. Playwright will download the browser automatically if not found.
 - Ensure your environment variables are set properly in the .env file (%USERPROFILE%\.ttclock.env on Windows).
 - Uses ntfy.sh for notifications (optional but recommended).
 - Tested on Linux, macOS, and Windows.
