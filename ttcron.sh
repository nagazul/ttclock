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
    local timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir" || {
            echo "[XID:$XID PID:$$] $timestamp [ERROR] [$(hostname -s)] [$(whoami)] - Failed to create log directory: $log_dir" >&2
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
    local timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    # Change to the script directory
    cd "$SCRIPT_DIR" || {
        echo "[XID:$XID PID:$$] $timestamp [ERROR] [$(hostname -s)] [$(whoami)] - Failed to change to script directory: $SCRIPT_DIR" >> "$LOGFILE" 2>&1
        return 3
    }
    
    # Activate virtual environment
    if [ -f .venv/bin/activate ]; then
        # shellcheck source=/dev/null
        source .venv/bin/activate || {
            timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
            echo "[XID:$XID PID:$$] $timestamp [ERROR] [$(hostname -s)] [$(whoami)] - Failed to activate virtual environment" >> "$LOGFILE" 2>&1
            return 4
        }
    else
        echo "[XID:$XID PID:$$] $timestamp [WARN ] [$(hostname -s)] [$(whoami)] - Virtual environment not found at expected location" >> "$LOGFILE" 2>&1
    fi
    
    # Log and execute the command
    echo "[XID:$XID PID:$$] $timestamp [INFO ] [$(hostname -s)] [$(whoami)] - Executing: python time.py $*" >> "$LOGFILE"
    python time.py "$@" >> "$LOGFILE" 2>&1
    local exit_code=$?
    
    timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    if [ $exit_code -ne 0 ]; then
        echo "[XID:$XID PID:$$] $timestamp [ERROR] [$(hostname -s)] [$(whoami)] - time.py exited with code $exit_code" >> "$LOGFILE" 2>&1
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
    
    # Use ISO 8601 format with millisecond precision for timestamps
    timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    
    {
        echo "[XID:$XID PID:$$] $timestamp [INFO ] [$(hostname -s)] [$(whoami)] - Starting ttcron.sh"
        echo "[XID:$XID PID:$$] $timestamp [INFO ] [$(hostname -s)] [$(whoami)] - Working directory: $SCRIPT_DIR"
        
        run_time "$@"
        local result=$?
        
        timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
        echo "[XID:$XID PID:$$] $timestamp [INFO ] [$(hostname -s)] [$(whoami)] - Completed ttcron.sh with exit code: $result"
    } >> "$LOGFILE" 2>&1
    
    exit $result
}

# Execute with all arguments
main "$@"
