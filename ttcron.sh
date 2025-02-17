#!/bin/bash

# Check if TTCRON is set
if [ -z "${TTCRON}" ]; then
    echo "Error: TTCRON environment variable is not set"
    echo "Please run this script via cron or set TTCRON manually"
    echo "Example: TTCRON=/path/to/ttcron.sh $0 in"
    exit 1
fi

# Extract path from TTCRON
TTPATH=$(dirname $(dirname ${TTCRON}))

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
    }
    
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
    }
    
    exec python time.py -q -r "$min_delay" "$max_delay" "$action"
}

# Main execution based on command argument
case "$1" in
    "in")
        setup_env
        run_time "in" 0 5
        ;;
    "out")
        setup_env
        run_time "out" 0 51
        ;;
    "auto")
        setup_env
        run_time "auto-out" 0 5
        ;;
    *)
        echo "Usage: TTCRON=/path/to/ttcron.sh $0 {in|out|auto}"
        exit 1
        ;;
esac
