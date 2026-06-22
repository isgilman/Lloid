#!/bin/bash
# Lloid schedule setup — edit times below and re-run to apply.
# Run with: ./setup_schedule.sh

# ── Schedule ─────────────────────────────────────────────────────────────────
FRI_START="15:00"   # 3:00 PM — server starts early so pmset wake at 2:55 PM covers it
FRI_STOP="23:00"    # 11:00 PM

SAT_START="15:00"   # 3:00 PM
SAT_STOP="23:00"    # 11:00 PM

SUN_START="15:00"   # 3:00 PM
SUN_STOP="20:00"    # 8:00 PM
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
START="$SCRIPT_DIR/start_lloid.sh"
STOP="$SCRIPT_DIR/stop_lloid.sh"

# Convert HH:MM to cron fields (minute hour)
cron_fields() { echo "${1#*:} ${1%%:*}"; }  # "18:00" → "00 18"

FRI_START_C=$(cron_fields "$FRI_START")
FRI_STOP_C=$(cron_fields "$FRI_STOP")
SAT_START_C=$(cron_fields "$SAT_START")
SAT_STOP_C=$(cron_fields "$SAT_STOP")
SUN_START_C=$(cron_fields "$SUN_START")
SUN_STOP_C=$(cron_fields "$SUN_STOP")

# pmset wake: 5 minutes before earliest start each day
wake_minus5() {
  local h="${1%%:*}" m="${1#*:}"
  m=$((10#$m - 5))
  if [ $m -lt 0 ]; then m=$((m + 60)); h=$((10#$h - 1)); fi
  printf "%02d:%02d:00" "$h" "$m"
}

FRI_WAKE=$(wake_minus5 "$FRI_START")
SAT_WAKE=$(wake_minus5 "$SAT_START")
SUN_WAKE=$(wake_minus5 "$SUN_START")

# ── Apply crontab ─────────────────────────────────────────────────────────────
NEW_CRON=$(cat <<EOF
# BEGIN LLOID
$FRI_START_C * * 5  $START
$FRI_STOP_C * * 5  $STOP
$SAT_START_C * * 6  $START
$SAT_STOP_C * * 6  $STOP
$SUN_START_C * * 0  $START
$SUN_STOP_C * * 0  $STOP
# END LLOID
EOF
)

# Strip existing Lloid block, then append new one
EXISTING=$(crontab -l 2>/dev/null | sed '/# BEGIN LLOID/,/# END LLOID/d')
(echo "$EXISTING"; echo "$NEW_CRON") | crontab -

echo "✓ Crontab updated:"
echo "$NEW_CRON"
echo ""

# ── Apply pmset wake ──────────────────────────────────────────────────────────
# Use the earliest start across all three days so one wake time covers everything.
# pmset repeat doesn't support multiple wakeorpoweron events, so we pick the min.
EARLIEST="$SAT_START"  # Sat/Sun 3 PM is earlier than Fri 6 PM
WAKE_TIME=$(wake_minus5 "$EARLIEST")
PMSET_CMD="sudo pmset repeat wakeorpoweron FSU $WAKE_TIME"

echo "Applying wake schedule (requires sudo):"
echo "  $PMSET_CMD"
eval "$PMSET_CMD"

echo ""
echo "Current schedule:"
pmset -g sched
echo ""
echo "Verify crontab with: crontab -l"
