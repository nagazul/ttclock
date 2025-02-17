#!/bin/bash

LOGFILE="$HOME/.ttcron.log"

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
    local max_delay=${3:-5}

    if [ ! -f "time.py" ]; then
        echo "Error: time.py not found in ${TTPATH}"
        exit 1
    fi

    python time.py -vv -r "$min_delay" "$max_delay" "$action" >> "$LOGFILE" 2>&1
}

# Main execution based on command argument
case "$1" in
    "in")
        setup_env
        run_time "in" 0 5
        ;;
    "out")
        setup_env
        run_time "out" 0 5
        ;;
    "auto")
        setup_env
        run_time "auto-out" 0 5
        ;;
    *)
        echo "Usage: $0 {in|out|auto}"
        exit 1
        ;;
esac

