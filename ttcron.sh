#!/bin/bash
# ttcron.sh - Time tracking automation wrapper for cron jobs (Playwright backend)
# Usage: ttcron.sh [OPTIONS] {in|out|auto-out}
# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOGFILE="${HOME}/.log/ttcron.log"
readonly MAX_LOG_SIZE=$((10 * 1024 * 1024))  # 10MB
readonly DEFAULT_ENV_FILE="${HOME}/.ttclock.env"

# Ensure common user bin directories are in PATH
export PATH="$PATH:$HOME/.local/bin:/usr/local/bin"

# Signal handler function
handle_exit() {
    local exit_code=$?
    local signal=$1
    local timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    
    # Only log if we're exiting due to a signal (not normal exit)
    if [ -n "$signal" ]; then
        echo "[XID:$XID PID:$PROCESS_ID] $timestamp [WARN ] [$HOSTNAME] [$USERNAME] - Received $signal signal. Script interrupted!" >> "$LOGFILE" 2>&1
        echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Completed ttcron.sh with exit code: 130 (interrupted)" >> "$LOGFILE" 2>&1
        
        # Force exit with appropriate code
        exit 130
    fi
}

# Ensure log directory exists and rotate log if needed
prepare_logging() {
    local log_dir=$(dirname "$LOGFILE")
    local timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    local process_id=$1
    
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir" || {
            echo "[XID:$XID PID:$process_id] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Failed to create log directory: $log_dir" >&2
            return 2
        }
    fi
    
    # Rotate log if it exceeds maximum size
    if [ -f "$LOGFILE" ] && [ $(stat -c%s "$LOGFILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]; then
        mv "$LOGFILE" "${LOGFILE}.old"
    fi

    return 0
}

# Find the uv command
find_uv() {
    # Try direct command
    if command -v uv >/dev/null 2>&1; then
        echo "uv"
        return 0
    fi
    
    # Try common locations
    for path in "$HOME/.local/bin/uv" "/usr/local/bin/uv" "/usr/bin/uv"; do
        if [ -x "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    
    # Not found
    local timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    echo "[XID:$XID PID:$PROCESS_ID] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Cannot locate uv command" >> "$LOGFILE" 2>&1
    return 1
}

# Execute ttclock with provided arguments
run_time() {
    local process_id=$1
    shift 1
    local timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    
    # Find uv command
    local UV_CMD=$(find_uv)
    if [ $? -ne 0 ]; then
        timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
        echo "[XID:$XID PID:$process_id] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Failed to find uv command" >> "$LOGFILE" 2>&1
        return 6
    fi
    
    cd "$SCRIPT_DIR" || {
        echo "[XID:$XID PID:$process_id] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Failed to change to script directory: $SCRIPT_DIR" >> "$LOGFILE" 2>&1
        return 3
    }

    # Set browser cache to uv's location to unify with ttclock
    export PLAYWRIGHT_BROWSERS_PATH="/home/roc3/.cache/uv/archive-v0"

    # Ensure Playwright browsers are installed
    echo "[XID:$XID PID:$process_id] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Installing Playwright browsers if needed" >> "$LOGFILE"
    $UV_CMD run playwright install >> "$LOGFILE" 2>&1
    
    if [ -f .venv/bin/activate ]; then
        source .venv/bin/activate || {
            timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
            echo "[XID:$XID PID:$process_id] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Failed to activate virtual environment" >> "$LOGFILE" 2>&1
            return 4
        }
    else
        echo "[XID:$XID PID:$process_id] $timestamp [WARN ] [$HOSTNAME] [$USERNAME] - Virtual environment not found at expected location" >> "$LOGFILE" 2>&1
    fi
    
    local env_arg=""
    if [ -n "$env_file" ] && [ -f "$env_file" ]; then
        env_arg="--env-file $env_file"
        echo "[XID:$XID PID:$process_id] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Using custom env file: $env_file" >> "$LOGFILE"
    elif [ -f "$DEFAULT_ENV_FILE" ]; then
        env_arg="--env-file $DEFAULT_ENV_FILE"
        echo "[XID:$XID PID:$process_id] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Using default env file: $DEFAULT_ENV_FILE" >> "$LOGFILE"
    else
        echo "[XID:$XID PID:$process_id] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - No .ttclock.env file found at $DEFAULT_ENV_FILE or specified path" >> "$LOGFILE" 2>&1
        return 5
    fi
    
    if command -v ttclock >/dev/null 2>&1; then
        echo "[XID:$XID PID:$process_id] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Executing: $UV_CMD run ttclock $env_arg $*" >> "$LOGFILE"
        $UV_CMD run ttclock $env_arg "$@" >> "$LOGFILE" 2>&1
        local exit_code=$?
    elif [ -f "$SCRIPT_DIR/ttclock.py" ]; then
        echo "[XID:$XID PID:$process_id] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Executing: $UV_CMD run python ttclock.py $env_arg $*" >> "$LOGFILE"
        $UV_CMD run python ttclock.py $env_arg "$@" >> "$LOGFILE" 2>&1
        local exit_code=$?
    else
        echo "[XID:$XID PID:$process_id] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Neither ttclock CLI nor ttclock.py found" >> "$LOGFILE" 2>&1
        return 1
    fi
    
    timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    if [ $exit_code -ne 0 ]; then
        echo "[XID:$XID PID:$process_id] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Command exited with code $exit_code" >> "$LOGFILE" 2>&1
        return $exit_code
    fi
    return 0
}

# Check probability and decide whether to execute
check_probability() {
    local chance=$1
    local roll=$(( RANDOM % 100 + 1 ))
    
    if [ $roll -le $chance ]; then
        return 0  # Run
    else
        return 1  # Skip
    fi
}

# Main execution
main() {
    # Get hostname and username once
    readonly HOSTNAME=$(hostname -s)
    readonly USERNAME=$(whoami)
    
    # Store the process ID
    readonly PROCESS_ID=$$
    
    # Set up signal traps for proper logging of interruptions
    trap 'handle_exit INT' INT
    trap 'handle_exit TERM' TERM
    trap 'handle_exit HUP' HUP
    trap 'handle_exit QUIT' QUIT
    
    # Generate session ID if not already set
    if [ -z "${XID:-}" ]; then
        export XID=$(date +%s%N | md5sum | head -c 8)
    fi
    
    # Prepare logging first
    prepare_logging $PROCESS_ID
    if [ $? -ne 0 ]; then
        exit 2
    fi
    
    # Use ISO 8601 format with millisecond precision for timestamps
    local timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    
    # Start logging
    echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Starting ttcron.sh" >> "$LOGFILE" 2>&1
    echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Working directory: $SCRIPT_DIR" >> "$LOGFILE" 2>&1
    
    # Parse arguments
    local chance=0
    local min_delay=0
    local max_delay=0
    local cmd_args=()
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --probability|--prob|-p)
                if [[ "$2" =~ ^[0-9]+$ ]] && [ "$2" -ge 0 ] && [ "$2" -le 100 ]; then
                    chance="$2"
                    shift 2
                elif [[ -z "$2" || "$2" =~ ^- ]]; then
                    # No value provided, use random probability between 0-100
                    chance=$(( RANDOM % 101 ))
                    shift 1
                else
                    timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
                    echo "[XID:$XID PID:$PROCESS_ID] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Invalid probability value: $2. Must be 0-100." >> "$LOGFILE" 2>&1
                    exit 5
                fi
                ;;
            --random-delay|-r)
                # Check if next two args exist and are numbers
                if [[ -n "$2" && "$2" =~ ^[0-9]+(\.[0-9]+)?$ && -n "$3" && "$3" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                    min_delay="$2"
                    max_delay="$3"
                    shift 3
                elif [[ -n "$2" && "$2" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                    # Only one number provided, use it as min and add 5 for max
                    min_delay="$2"
                    max_delay=$(echo "$min_delay + 5" | bc)
                    shift 2
                elif [[ -z "$2" || "$2" =~ ^- ]]; then
                    # No values provided, use default 0-5 minutes
                    min_delay=0
                    max_delay=5
                    shift 1
                else
                    timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
                    echo "[XID:$XID PID:$PROCESS_ID] $timestamp [ERROR] [$HOSTNAME] [$USERNAME] - Invalid random delay values. Must be numbers." >> "$LOGFILE" 2>&1
                    exit 6
                fi
                ;;
            *)
                cmd_args+=("$1")
                shift
                ;;
        esac
    done
    
    # Check probability if set
    if [ $chance -gt 0 ]; then
        timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
        
        # Log the probability check
        if [ $chance -eq $(( RANDOM % 101 )) ]; then
            echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Checking probability: $chance% (randomly generated)" >> "$LOGFILE" 2>&1
        else
            echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Checking probability: $chance%" >> "$LOGFILE" 2>&1
        fi
        
        # Perform the probability check
        if ! check_probability "$chance"; then
            timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
            echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Skipping execution based on probability ($chance%)" >> "$LOGFILE" 2>&1
            
            # Important: Exit here with success
            timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
            echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Completed ttcron.sh with exit code: 0" >> "$LOGFILE" 2>&1
            exit 0
        fi
        
        timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
        echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Continuing execution based on probability ($chance%)" >> "$LOGFILE" 2>&1
    fi
    
    # Apply random delay if set
    if [ $(echo "$max_delay > 0" | bc -l) -eq 1 ]; then
        # Calculate random delay between min and max (in seconds)
        # We multiply by 100 to get precision for bc calculation
        local range=$(echo "($max_delay - $min_delay) * 100" | bc -l)
        local random_offset=$(( RANDOM % (${range%.*} + 1) ))
        local delay_minutes=$(echo "scale=2; $min_delay + $random_offset / 100" | bc -l)
        local delay_seconds=$(echo "scale=2; $delay_minutes * 60" | bc -l)
        
        timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
        echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Waiting for random delay: $delay_minutes minutes" >> "$LOGFILE" 2>&1
        
        # Convert to integer seconds for sleep
        sleep ${delay_seconds%.*}
        
        timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
        echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Random delay completed" >> "$LOGFILE" 2>&1
    fi
    
    # Execute the ttclock script with remaining arguments
    run_time "$PROCESS_ID" "${cmd_args[@]}"
    local result=$?
    
    # Log completion
    timestamp=$(date '+%Y-%m-%dT%H:%M:%S.%3N%z')
    echo "[XID:$XID PID:$PROCESS_ID] $timestamp [INFO ] [$HOSTNAME] [$USERNAME] - Completed ttcron.sh with exit code: $result" >> "$LOGFILE" 2>&1
    
    exit $result
}

# Execute with all arguments
main "$@"
