#!/bin/bash

# ttcron.sh - Time tracking automation wrapper for cron jobs
# Usage: ttcron.sh [OPTIONS] {in|out|auto-out}
# See time.py --help for full options list

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOGFILE="${HOME}/.log/ttcron.log"

# Ensure log directory exists
ensure_log_dir() {
    local log_dir=$(dirname "$LOGFILE")
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir" || {
            echo "Error: Failed to create log directory: $log_dir" >&2
            exit 2
        }
    fi
}

# Execute time.py with provided arguments
run_time() {
    # Change to the script directory first
    cd "$SCRIPT_DIR" || {
        echo "Error: Failed to change to script directory: $SCRIPT_DIR" >&2
        exit 3
    }
    
    # Log the current directory
    echo "Working directory: $(pwd)" >> "$LOGFILE"
    
    # Activate virtual environment
    # shellcheck source=/dev/null
    source .venv/bin/activate || {
        echo "Error: Failed to activate virtual environment" >&2
        exit 4
    }
    
    # Log and execute the command with provided arguments as-is
    echo "Executing: python time.py -vv $*" >> "$LOGFILE"
    python time.py -vv "$@" >> "$LOGFILE" 2>&1 || {
        echo "Error: Failed to execute time.py with arguments: $*" >&2
        exit 1
    }
}

# Main execution
main() {
    ensure_log_dir
    echo "-------------------------" >> "$LOGFILE"
    echo "Starting ttcron.sh at $(date)" >> "$LOGFILE"
    run_time "$@"
    echo "Completed ttcron.sh at $(date)" >> "$LOGFILE"
    echo "-------------------------" >> "$LOGFILE"
}

# Execute with all arguments
main "$@"
