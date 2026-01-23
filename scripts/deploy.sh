#!/bin/bash
# scripts/deploy.sh - Triggered by webhook_listener.py

set -e

PROJECT_ROOT="/home/maric/PycharmProjects/Okysa"
GAMEPACK_ROOT="/home/maric/PycharmProjects/GamePack"

echo "[$(date)] Starting redeployment..."

# 1. Update GamePack
echo "Updating GamePack..."
cd "$GAMEPACK_ROOT"
git pull

# 2. Update Okysa
echo "Updating Okysa..."
cd "$PROJECT_ROOT"
git pull

# 3. Sync dependencies with uv
echo "Syncing dependencies..."
uv sync --all-extras

# 4. Restart the bot
echo "Restarting okysa.service..."
sudo systemctl restart okysa.service

echo "[$(date)] Deployment successful!"
