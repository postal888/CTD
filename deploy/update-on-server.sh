#!/bin/bash
# Run ON the server to update code from GitHub. Keeps existing .env (OPENAI_API_KEY etc.).
set -e
APP_DIR="/var/www/crackthedeck"
cd "$APP_DIR"
git fetch origin
git reset --hard origin/main
sudo systemctl restart crackthedeck-backend
echo "Updated. Backend restarted. Check: sudo systemctl status crackthedeck-backend"
