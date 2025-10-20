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
