#!/bin/bash
# Start Lloid bar server (called by cron)
LOG="/Users/iangilman/Dropbox/Projects/Lloid/lloid-cron.log"

# Already running? Nothing to do.
if pgrep -f "python app.py" > /dev/null 2>&1; then
  echo "$(date): Lloid already running — skipping start" >> "$LOG"
  exit 0
fi

cd /Users/iangilman/Dropbox/Projects/Lloid

nohup /Users/iangilman/miniconda3/bin/python app.py >> "$LOG" 2>&1 &
LLOID_PID=$!

# Keep the Mac awake for exactly as long as Lloid is running
nohup /usr/bin/caffeinate -i -w $LLOID_PID > /dev/null 2>&1 &

echo "$(date): Lloid started (PID $LLOID_PID)" >> "$LOG"
