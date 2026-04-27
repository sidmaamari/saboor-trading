#!/bin/bash
# One-time setup for Saboor on a DigitalOcean Ubuntu 22.04 droplet.
# Run as root after SSH-ing in for the first time.
# Usage: bash setup.sh

set -e

REPO="https://github.com/sidmaamari/saboor-trading.git"
INSTALL_DIR="/opt/saboor"

echo "=== Installing system dependencies ==="
apt-get update -qq
apt-get install -y python3 python3-pip git cron

echo "=== Cloning repo ==="
git clone "$REPO" "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "=== Installing Python packages ==="
pip3 install -r requirements.txt

echo "=== Creating logs directory ==="
mkdir -p "$INSTALL_DIR/logs"

echo "=== Creating .env.local ==="
cat > "$INSTALL_DIR/.env.local" << 'ENVEOF'
ANTHROPIC_API_KEY=REPLACE_ME
ALPACA_API_KEY=REPLACE_ME
ALPACA_SECRET_KEY=REPLACE_ME
ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2
TELEGRAM_BOT_TOKEN=REPLACE_ME
TELEGRAM_CHAT_ID=REPLACE_ME
SUPABASE_URL=REPLACE_ME
SUPABASE_SERVICE_KEY=REPLACE_ME
ENVEOF

echo ""
echo ">>> IMPORTANT: Edit /opt/saboor/.env.local and replace each REPLACE_ME with the real key."
echo ">>> Then run:  bash /opt/saboor/deploy/install_cron.sh"
echo ""
echo "Setup complete."
