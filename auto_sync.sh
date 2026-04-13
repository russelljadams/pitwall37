#!/bin/bash
# Auto-sync and parse new IBT files from GPU box
# Designed to run via cron

cd /home/gh0st/projects/pitwall37

# Sync
NEW=$(bash sync.sh 2>&1 | grep "new files copied" | grep -o '[0-9]*' | head -1)

# Parse if new files found
if [ "$NEW" -gt 0 ] 2>/dev/null; then
    venv/bin/python3 ibt_parser.py 2>&1 | tail -1
fi
