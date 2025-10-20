# Field Notes from ttclock Project
# Tricky/non-obvious lessons, plain text format

# Playwright Browser Cache Differences
# uv run python installs in ~/.cache/ms-playwright (unpacked, ~1.1G)
# Direct python uses uv cache (~/.cache/uv/archive-v0, compressed, ~140M)
# Unify with PLAYWRIGHT_BROWSERS_PATH in .env or script
# Prevents 10x size difference and duplicates

# SSH Key Auth Issues
# Use %n in key comments for proper formatting
# Ensure key added to correct GitHub account (check SHA256)
# Explicit -i may still fail if key on wrong account

# Cron Script Argument Passing Bug
# run_time() shifted args incorrectly, consuming command args
# Fix: Change shift 2 to shift 1 when no env_file param
# Caused ttclock to run without 'out' or other args

# Playwright Migration from Selenium
# Async context: async with playwright() as p: browser = await p.chromium.launch()
# Better reliability, but cache management tricky

# Cron Human-like Scheduling
# Multiple times + probability + random delays for spread
# Example: 15,45 6-7 * * 1-5 ttcron.sh -p 60 -r 1 15 in</content>
</xai:function_call />

<xai:function_call name="read">
<parameter name="filePath">AGENTS.md