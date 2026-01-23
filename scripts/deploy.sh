#!/bin/bash
# scripts/deploy.sh - Triggered by webhook_listener.py

set -e

# Find project root relative to script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Assuming GamePack is in the same parent directory as Okysa
PARENT_DIR="$(dirname "$PROJECT_ROOT")"
GAMEPACK_ROOT="${GAMEPACK_ROOT:-$PARENT_DIR/GamePack}"

echo "[$(date)] Starting redeployment in $PROJECT_ROOT..."

# 1. Update GamePack
if [ -d "$GAMEPACK_ROOT" ]; then
    echo "Updating GamePack at $GAMEPACK_ROOT..."
    cd "$GAMEPACK_ROOT"
    git pull
else
    echo "WARNING: GamePack directory not found at $GAMEPACK_ROOT. Skipping update."
fi

# 2. Update Okysa
echo "Updating Okysa at $PROJECT_ROOT..."
cd "$PROJECT_ROOT"
git pull

# 3. Sync dependencies with uv
echo "Syncing dependencies..."
uv sync --all-extras

# 4. Restart the bot
echo "Restarting okysa.service..."
sudo systemctl restart okysa.service

echo "[$(date)] Deployment successful!"
