#!/bin/bash

# ttcron.sh - Time tracking automation wrapper for cron jobs
# Usage: ttcron.sh [OPTIONS] {in|out|auto-out}
# See time.py --help for full options list

# Configuration
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
    # shellcheck source=/dev/null
    source .venv/bin/activate

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
    run_time "$@"
}

# Execute with all arguments
main "$@"
