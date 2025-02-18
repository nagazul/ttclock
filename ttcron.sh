#!/bin/bash

LOGFILE="$HOME/.log/ttcron.log"

# Extract the directory path from the LOGFILE variable
LOGDIR=$(dirname "$LOGFILE")

# Check if the directory exists, if not, create it
if [ ! -d "$LOGDIR" ]; then
    mkdir -p "$LOGDIR"
    echo "Directory $LOGDIR created."
fi

# Get the script's directory
TTPATH=$(dirname "$(realpath "$0")")

# Function to ensure we're in the right directory and virtual environment
setup_env() {
    if [ ! -d "${TTPATH}" ]; then
        echo "Error: Directory ${TTPATH} does not exist"
        exit 1
    fi
    cd "${TTPATH}" || exit 1
    if [ ! -d ".venv" ]; then
        echo "Error: Virtual environment not found in ${TTPATH}"
        exit 1
    fi
    source .venv/bin/activate
}

# Function to execute time.py with common parameters
run_time() {
    local action=$1
    local min_delay=${2:-0}
    local max_delay=${3:-0}
    local notify_flag=$4
    local env_file=$5

    if [ ! -f "time.py" ]; then
        echo "Error: time.py not found in ${TTPATH}"
        exit 1
    fi

    # Build the command with optional parameters
    local cmd="python time.py -vv"
    
    # Add notification flag if specified
    if [ "$notify_flag" = true ]; then
        cmd="$cmd -n"
    fi
    
    # Add random delay if specified
    if [ "$min_delay" != "0" ] || [ "$max_delay" != "0" ]; then
        cmd="$cmd -r $min_delay $max_delay"
    fi
    
    # Add env-file if specified
    if [ -n "$env_file" ]; then
        if [ -f "$env_file" ]; then
            cmd="$cmd --env-file $env_file"
        else
            echo "Error: Specified env-file '$env_file' does not exist"
            exit 1
        fi
    fi
    
    # Add the action and execute
    cmd="$cmd $action"
    eval "$cmd >> $LOGFILE 2>&1"
}

# Parse command line options
NOTIFY=false
COMMAND=""
ENV_FILE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --ntfy)
            NOTIFY=true
            shift
            ;;
        --env-file)
            if [ -z "$2" ]; then
                echo "Error: --env-file requires a path argument"
                echo "Usage: $0 [--ntfy] [--env-file PATH] {in|out|auto}"
                exit 1
            fi
            ENV_FILE="$2"
            shift 2
            ;;
        in|out|auto)
            COMMAND="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--ntfy] [--env-file PATH] {in|out|auto}"
            exit 1
            ;;
    esac
done

# Check if command is provided
if [ -z "$COMMAND" ]; then
    echo "Usage: $0 [--ntfy] [--env-file PATH] {in|out|auto}"
    exit 1
fi

# Main execution based on command argument
case "$COMMAND" in
    "in")
        setup_env
        run_time "in" 0 5 "$NOTIFY" "$ENV_FILE"
        ;;
    "out")
        setup_env
        run_time "out" 0 5 "$NOTIFY" "$ENV_FILE"
        ;;
    "auto")
        setup_env
        run_time "auto-out" 0 5 "$NOTIFY" "$ENV_FILE"
        ;;
    *)
        echo "Usage: $0 [--ntfy] [--env-file PATH] {in|out|auto}"
        exit 1
        ;;
esac
