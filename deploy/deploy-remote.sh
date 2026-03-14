#!/bin/bash
# Run this script ON the server 165.22.212.230 (e.g. via SSH).
# From local: ssh root@165.22.212.230 'bash -s' < deploy/deploy-remote.sh
# Or: ssh into server, then: cd /var/www/crackthedeck && bash deploy/deploy-remote.sh
set -e
SERVER_IP="${SERVER_IP:-165.22.212.230}"
APP_DIR="/var/www/crackthedeck"
REPO_URL="https://github.com/postal888/CTD.git"

echo "=== CrackTheDeck deploy to $SERVER_IP ==="

# 1. Install dependencies
echo "Checking system dependencies..."
if ! command -v python3 &>/dev/null; then
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip nginx poppler-utils libreoffice
else
  for cmd in nginx pdftoppm libreoffice; do
    if ! command -v $cmd &>/dev/null; then
      sudo apt update
      sudo apt install -y nginx poppler-utils libreoffice
      break
    fi
  done
fi
# Prefer Python 3.11 if available (optional)
if command -v python3.11 &>/dev/null; then
  sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 2>/dev/null || true
fi

# 2. Prepare directory and clone/update repo
sudo mkdir -p "$APP_DIR"
sudo chown "$USER:$USER" "$APP_DIR"
cd "$APP_DIR"

if [ -d ".git" ]; then
  echo "Updating existing repo..."
  git fetch origin
  git reset --hard origin/main
else
  echo "Cloning from GitHub..."
  TMP_CLONE="/tmp/ctd-clone-$$"
  git clone "$REPO_URL" "$TMP_CLONE"
  cp -a "$TMP_CLONE"/. "$APP_DIR"/
  rm -rf "$TMP_CLONE"
fi

# 3. Run server setup (nginx, systemd, venv, permissions)
chmod +x deploy/server-setup.sh
./deploy/server-setup.sh "$SERVER_IP"

echo ""
echo "=== Next step ==="
echo "Set your OpenAI API key on the server:"
echo "  sudo nano $APP_DIR/crackthedeck-backend/crackthedeck-backend/.env"
echo "  # Set: OPENAI_API_KEY=sk-..."
echo "  sudo systemctl restart crackthedeck-backend"
echo ""
echo "Then open: http://$SERVER_IP"
exit 0
