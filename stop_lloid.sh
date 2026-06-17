#!/bin/bash
# Stop Lloid bar server (called by cron)
LOG="/Users/iangilman/Dropbox/Projects/Lloid/lloid-cron.log"

pkill -f "python app.py" 2>/dev/null || true
lsof -ti :5001 | xargs kill -9 2>/dev/null || true
# caffeinate exits automatically when the python process dies

echo "$(date): Lloid stopped" >> "$LOG"
