#!/bin/bash

# ttcron.sh - Time tracking automation wrapper for cron jobs
# Usage: ttcron.sh [OPTIONS] {in|out|auto-out}

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOGFILE="${HOME}/.log/ttcron.log"
readonly MAX_LOG_SIZE=$((10 * 1024 * 1024))  # 10MB

# Ensure log directory exists and rotate log if needed
prepare_logging() {
    local log_dir=$(dirname "$LOGFILE")
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir" || {
            echo "Error: Failed to create log directory: $log_dir" >&2
            exit 2
        }
    fi
    
    # Rotate log if it exceeds maximum size
    if [ -f "$LOGFILE" ] && [ $(stat -c%s "$LOGFILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]; then
        mv "$LOGFILE" "${LOGFILE}.old"
    fi
}

# Execute time.py with provided arguments
run_time() {
    # Change to the script directory
    cd "$SCRIPT_DIR" || {
        echo "Error: Failed to change to script directory: $SCRIPT_DIR" >> "$LOGFILE" 2>&1
        return 3
    }
    
    # Activate virtual environment
    if [ -f .venv/bin/activate ]; then
        # shellcheck source=/dev/null
        source .venv/bin/activate || {
            echo "Error: Failed to activate virtual environment" >> "$LOGFILE" 2>&1
            return 4
        }
    else
        echo "Warning: Virtual environment not found at expected location" >> "$LOGFILE" 2>&1
    fi
    
    # Log and execute the command
    echo "[Session $XID PID $$] Executing: python time.py $*" >> "$LOGFILE"
    python time.py "$@" >> "$LOGFILE" 2>&1
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        echo "[Session $XID PID $$] Error: time.py exited with code $exit_code" >> "$LOGFILE" 2>&1
        return $exit_code
    fi
    
    return 0
}

# Main execution
main() {
    prepare_logging
    
    # Generate session ID if not already set
    if [ -z "${XID:-}" ]; then
        export XID=$(date +%s%N | md5sum | head -c 8)
    fi
    
    {
        echo "-------------------------"
        echo "[XID $XID PID $$] Starting ttcron.sh at $(date)"
        echo "[XID $XID PID $$] User: $(whoami)"
        echo "[XID $XID PID $$] Working directory: $SCRIPT_DIR"
        
        run_time "$@"
        local result=$?
        
        echo "[XID $XID PID $$] Completed ttcron.sh at $(date) with exit code: $result"
        echo "-------------------------"
    } >> "$LOGFILE" 2>&1
    
    exit $result
}

# Execute with all arguments
main "$@"
