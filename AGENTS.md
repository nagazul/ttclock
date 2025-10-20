README Style Guide

All README files must follow this format for consistency and usability. Assume reader has fair Linux experience.

- Plain text only: No markdown syntax (no #, *, `, etc.)
- No backticks: Commands are written directly without code blocks
- Commands start from the beginning of the line: No leading spaces or indentation for easy copy/paste
- One-line comments above commands: Succinct # comments for engineers, assume basic knowledge
- Keep it brief and practical: Focus on essential info, avoid verbose explanations
- Structure: Intro, Installation, Configuration, Usage with examples, Troubleshooting, Security

Comment style: Technical, concise, e.g., "# List files" not "# This command lists all the files"

Heredoc usage: Use <<EOF for multi-line strings in bash scripts. Start from line beginning for copy/paste.

Example heredoc:
cat <<EOF
Multi-line
content here
EOF

Example format:
# List files
ls

# Search for pattern
grep "pattern" file.txt

# Maintaining LESSONS.md
# Document tricky/non-obvious issues during development
# Format: # Topic\n# Description\n# Example if applicable
# Keep only non-obvious lessons to avoid clutter

# Lessons Learned from ttclock Project
# Plain text format for consistency, commands and examples directly usable

# Migration from Selenium to Playwright
# Playwright offers better performance, reliability, and cross-platform support
# Replace webdriver with async browser context
# Example: browser = await p.chromium.launch(); page = await browser.new_page()

# Code Modularization
# Split large files into focused modules for maintainability
# ttclock/__init__.py: Entry point
# ttclock/cli.py: Argument parsing and main flow
# ttclock/automation.py: Browser automation logic
# ttclock/utils.py: Shared utilities (logging, notifications, etc.)

# Cron Scheduling with Human-like Randomness
# Use probability (-p) and random delays (-r) to avoid predictable patterns
# Example cron: 15,45 6-7 * * 1-5 ttcron.sh -p 60 -r 1 15 in
# Multiple times per window for spread: 15,45 6-7 covers 6:15,6:45,7:15,7:45

# Playwright Browser Cache Management
# Browsers installed in ~/.cache/ms-playwright or uv cache (~/.cache/uv/archive-v0)
# To unify caches: export PLAYWRIGHT_BROWSERS_PATH=/path/to/cache
# Add to .env: PLAYWRIGHT_BROWSERS_PATH=/home/user/.cache/uv/archive-v0
# Prevents duplicate downloads (1.1G vs 140M compressed)

# SSH Key Management for GitHub
# Ensure correct key added to GitHub account (check SHA256 fingerprint)
# Use ssh -i ~/.ssh/id_key -T git@github.com to test auth
# Config ~/.ssh/config: Host github.com; User git; IdentityFile ~/.ssh/id_key

# Script Debugging and Fixes
# Check argument passing: run_time function consumed args incorrectly
# Fix: Change shift 2 to shift 1 in run_time()
# Add logging for troubleshooting cron jobs

# Python Package Management with uv
# uv venv: Create virtual environment
# uv sync: Install dependencies from pyproject.toml
# uv run: Execute commands in venv context
# Faster than pip, handles lockfiles

# Environment Variables and Configuration
# Use .env files for sensitive data (credentials, paths)
# Load with python-dotenv: load_dotenv()
# Separate example file: .env.example with placeholders

# Error Handling in Async Code
# Use try/except in async functions
# Example: async with playwright() as p: try: ... except Exception as e: print(e)

# Git Workflow
# Commit logical changes with clear messages
# Use git status/add/commit for tracking
# Push after local commits ready

# Cross-Platform Compatibility
# Test on Linux, macOS, Windows
# Use pathlib for paths, os for environment
# Handle different cache locations per OS</content>
</xai:function_call />

<xai:function_call name="bash">
<parameter name="command">git add LESSONS.txt AGENTS.md