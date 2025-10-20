import argparse
import json
import sys
import os
import random
import time
import signal
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from .utils import setup_logging, load_environment, check_probability
from .automation import TimeCheckAutomation


# --- Global Signal Handler ---
# Keep track of the current automation instance for cleanup
current_automation_instance = None

def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    import logging
    signal_name = signal.Signals(signum).name
    print(f"\nReceived signal {signal_name} ({signum}). Shutting down gracefully...", file=sys.stderr)
    logging.getLogger('ttclock').warning(f"Received signal {signal_name} ({signum}). Initiating graceful shutdown.")
    if current_automation_instance:
        current_automation_instance.cleanup()
    logging.getLogger('ttclock').info("Cleanup complete. Exiting.")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler) # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # kill command


def parse_arguments():
    """Parse command line arguments with improved handling for optional args."""
    parser = argparse.ArgumentParser(
        description='Automates interactions with a time tracking website.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help
    )

    # Action argument (positional or optional)
    # Using a subparsers approach might be cleaner for distinct actions,
    # but sticking to the original structure for now.
    parser.add_argument(
        'action',
        nargs='?', # Makes the action optional
        choices=['in', 'out', 'switch', 'status', 'auto-out'],
        default='status', # Default action if none is provided
        help='The primary action to perform: clock "in", clock "out", "switch" state, check "status", or perform "auto-out" based on time left.'
    )

    # Notification control
    notification_group = parser.add_mutually_exclusive_group()
    notification_group.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress all non-error output and disable notifications (overrides -n and NTFY_TOPIC).'
    )
    notification_group.add_argument(
        '-n', '--ntfy',
        action='store_true',
        help='Enable notifications via ntfy.sh (requires NTFY_TOPIC env var). Ignored if -q is used.'
    )

    # Verbosity
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase logging verbosity (-v: INFO, -vv: DEBUG script/WARN libs, -vvv: DEBUG all). Errors are always logged.'
    )

    # Random Delay
    parser.add_argument(
        '-r', '--random-delay',
        nargs='*', # 0 or more arguments
        type=float,
        metavar=('MIN', 'MAX'),
        help='Wait for a random duration between MIN and MAX minutes before executing the action. If only MIN is given, MAX is MIN+5. If no values are given, defaults to 0-5 minutes.'
    )

    # Probability
    parser.add_argument(
        '-p', '--probability', '--prob',
        type=int,
        metavar='PERCENT',
        default=100, # Default to 100% probability (always run)
        help='An integer percentage (0-100) representing the chance the script will execute the main action. Default is 100.'
    )

    # Environment File
    parser.add_argument(
        '--env-file',
        type=str,
        metavar='FILEPATH',
        help='Path to a custom .env file to load environment variables from (overrides default .env).'
    )

    # --- Argument Validation and Processing ---
    args = parser.parse_args()

    # Validate probability
    if not (0 <= args.probability <= 100):
        parser.error("Probability must be an integer between 0 and 100.")

    # Process random_delay
    if args.random_delay is not None: # Check if the flag was present
        if len(args.random_delay) == 0:
            args.random_delay = (0.0, 5.0) # Default range 0-5 mins
        elif len(args.random_delay) == 1:
            min_delay = args.random_delay[0]
            if min_delay < 0: parser.error("Minimum delay cannot be negative.")
            args.random_delay = (min_delay, min_delay + 5.0) # Single value means min to min+5
        elif len(args.random_delay) == 2:
            min_delay, max_delay = args.random_delay
            if min_delay < 0 or max_delay < 0: parser.error("Delay values cannot be negative.")
            if min_delay > max_delay: parser.error("Minimum delay cannot be greater than maximum delay.")
            args.random_delay = (min_delay, max_delay) # Use provided range
        else:
            parser.error("Argument --random-delay: expected 0, 1, or 2 values.")
    # If --random-delay was not provided, args.random_delay remains None

    return args


def main():
    """Main execution function"""
    global current_automation_instance # Allow modification of the global instance tracker

    args = parse_arguments()
    logger = setup_logging(args.verbose if not args.quiet else -1) # Pass -1 or similar if quiet to ensure minimal logging

    # Log the command execution details
    command_line = f"{sys.executable} {' '.join(sys.argv)}"
    logger.info(f"Script started. Command: {command_line}")
    logger.debug(f"Parsed arguments: {args}")

    load_environment(args.env_file)

    # --- Probability Check ---
    if args.probability < 100:
        logger.info(f"Checking probability: {args.probability}% chance to execute.")
        if not check_probability(args.probability):
            logger.info(f"Skipping execution based on probability check (rolled > {args.probability}).")
            sys.exit(0) # Exit cleanly
        else:
            logger.info(f"Proceeding with execution based on probability check (rolled <= {args.probability}).")


    # --- Random Delay ---
    if args.random_delay:
        min_delay, max_delay = args.random_delay
        delay_secs = random.uniform(min_delay * 60, max_delay * 60)
        logger.info(f"Applying random delay: waiting for {delay_secs:.2f} seconds ({delay_secs/60:.2f} minutes)...")
        try:
            time.sleep(delay_secs)
        except KeyboardInterrupt:
            # signal_handler will be invoked automatically by the system
            logger.warning("Delay interrupted by user.")
            # The signal handler should exit, but add an explicit exit just in case.
            sys.exit(1)


    # --- Execute Action ---
    automation = None # Initialize to None
    exit_code = 0
    try:
        # Determine notification enablement based on args and env var
        # Quiet flag takes precedence
        enable_notifications = not args.quiet and args.ntfy and bool(os.getenv('NTFY_TOPIC'))
        automation = TimeCheckAutomation(quiet=args.quiet or not enable_notifications)
        current_automation_instance = automation # Register instance for signal handler

        logger.info(f"Executing action: {args.action}")

        if args.action == 'status':
            time_info = automation.run_status_check()
            # Print JSON output for status check
            try:
                  print(json.dumps(time_info, indent=2), file=sys.stdout)
            except TypeError as e:
                  logger.error(f"Failed to serialize time_info to JSON: {e}")
                  print(f"Raw time info: {time_info}", file=sys.stderr) # Print raw dict as fallback
        elif args.action == 'auto-out':
            automation.run_auto_out()
        elif args.action in ['in', 'out', 'switch']:
            automation.run_clock_action(args.action)
        else:
            # This case should not be reachable due to argparse choices
            logger.error(f"Internal error: Unhandled action '{args.action}'")
            exit_code = 2

        logger.info(f"Action '{args.action}' completed.")

    except (PlaywrightTimeoutError, PlaywrightError, ValueError, RuntimeError) as e:
        logger.critical(f"Script execution failed: {type(e).__name__} - {str(e)}")
        # Specific error logging and notifications are handled within the methods
        exit_code = 1 # Indicate failure
    except KeyboardInterrupt:
        logger.warning("Script execution interrupted by user (main loop).")
        # Signal handler should manage cleanup and exit.
        exit_code = 130 # Standard exit code for SIGINT
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred in main execution: {str(e)}", exc_info=True)
        # Send a final notification for unexpected errors if possible
        if automation:
              automation.send_notification(f"Critical script error: {str(e)}", priority="high", tags=["main", "error", "unexpected"], force=True)
        exit_code = 1 # Indicate failure
    finally:
        # Ensure cleanup runs even if automation object wasn't fully initialized in edge cases
        if current_automation_instance and current_automation_instance.page:
            logger.debug("Performing final cleanup check in main finally block.")
            current_automation_instance.cleanup()
        current_automation_instance = None # Deregister instance

    logger.info(f"Script finished with exit code {exit_code}.")
    sys.exit(exit_code)