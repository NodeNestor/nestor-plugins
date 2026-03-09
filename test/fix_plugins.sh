#!/bin/bash
# Fix plugin scripts that lose execute permissions from Windows volume mounts
# and fix CRLF line endings

PLUGINS_DIR="$HOME/.claude/plugins"

if [ -d "$PLUGINS_DIR" ]; then
    for plugin in "$PLUGINS_DIR"/*/; do
        # Fix line endings on shell scripts
        find "$plugin" -name "*.sh" -exec sed -i 's/\r$//' {} \; 2>/dev/null
        # Fix execute permissions
        find "$plugin" -name "*.sh" -exec chmod +x {} \; 2>/dev/null
        # Fix line endings on Python files too
        find "$plugin" -name "*.py" -exec sed -i 's/\r$//' {} \; 2>/dev/null
        echo "Fixed plugin: $(basename "$plugin")"
    done
fi

exec python3 /app/live_test.py
