#!/bin/bash
# Pull latest code from GitHub without touching .env.local.
# Run this whenever you push new changes.
# Usage: bash /opt/saboor/deploy/update.sh

set -e
cd /opt/saboor
git pull origin main
venv/bin/pip install -r requirements.txt --quiet
echo "Update complete."
