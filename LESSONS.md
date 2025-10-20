# Field Notes from ttclock Project
# Tricky/non-obvious lessons, plain text format

# Playwright Browser Cache Management
# Uses system Chrome/Chromium if available and compatible, no download/cache
# If system browser incompatible (e.g., old headless removed), installs bundled in ~/.cache/ms-playwright (~340MB unpacked: Chromium 164MB, Firefox 86MB, Webkit 90MB)
# To unify with uv cache: PLAYWRIGHT_BROWSERS_PATH=/home/user/.cache/uv/archive-v0 in .env (compressed to ~140MB)
# Prevents duplicate downloads and size issues

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