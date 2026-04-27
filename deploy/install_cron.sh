#!/bin/bash
# Installs the Saboor cron schedule (UTC times).
# Run this after setup.sh and after filling in .env.local.
# Usage: bash install_cron.sh

INSTALL_DIR="/opt/saboor"
PYTHON="$INSTALL_DIR/venv/bin/python3"
LOG="$INSTALL_DIR/logs"

# Remove any existing Saboor cron entries, then add fresh ones
(crontab -l 2>/dev/null | grep -v saboor; cat << CRONEOF
# Saboor trading agent — all times UTC (Oman = UTC+4, US Eastern market hours)
30 11 * * 1-5 cd $INSTALL_DIR && $PYTHON main.py premarket >> $LOG/premarket.log 2>&1
35 13 * * 1-5 cd $INSTALL_DIR && $PYTHON main.py open      >> $LOG/open.log      2>&1
0  16 * * 1-5 cd $INSTALL_DIR && $PYTHON main.py midday    >> $LOG/midday.log    2>&1
30 19 * * 1-5 cd $INSTALL_DIR && $PYTHON main.py eod       >> $LOG/eod.log       2>&1
CRONEOF
) | crontab -

echo "Cron installed. Current schedule:"
crontab -l
