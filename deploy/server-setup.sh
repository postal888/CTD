#!/bin/bash
# Run on server after copying project to /var/www/crackthedeck
# Usage: ./server-setup.sh [YOUR_DOMAIN_OR_IP]
# Example: ./server-setup.sh crackthedeck.com
# Example: ./server-setup.sh 165.22.212.230
set -e
APP_DIR=/var/www/crackthedeck
BACKEND_DIR=$APP_DIR/crackthedeck-backend/crackthedeck-backend
DOMAIN="${1:-YOUR_DOMAIN_OR_IP}"

echo "=== Remove Windows poppler (use system pdftoppm) ==="
rm -rf "$BACKEND_DIR/poppler-25.12.0" 2>/dev/null || true

echo "=== Python venv and dependencies ==="
cd "$APP_DIR"
python3 -m venv venv
./venv/bin/pip install -q -r "$BACKEND_DIR/requirements.txt"

echo "=== .env from example ==="
cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
echo "Edit $BACKEND_DIR/.env: set OPENAI_API_KEY=sk-... (and optionally FUNDS_RAG_URL=http://127.0.0.1:8100 if running funds-rag)"

echo "=== Nginx ==="
sudo sed "s/YOUR_DOMAIN_OR_IP/$DOMAIN/g" "$APP_DIR/deploy/nginx-crackthedeck.conf" | sudo tee /etc/nginx/sites-available/crackthedeck > /dev/null
sudo ln -sf /etc/nginx/sites-available/crackthedeck /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
sudo nginx -t && sudo systemctl reload nginx

echo "=== Systemd service ==="
sudo cp "$APP_DIR/deploy/crackthedeck-backend.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable crackthedeck-backend

echo "=== Permissions (www-data) ==="
sudo chown -R www-data:www-data "$APP_DIR/crackthedeck-backend" "$APP_DIR/crackthedeck-deploy"
sudo chmod -R o+rX "$APP_DIR/venv" 2>/dev/null || true
sudo chmod -R o+rX "$APP_DIR/venv"

echo "=== Start backend ==="
sudo systemctl start crackthedeck-backend
sleep 2
sudo systemctl status crackthedeck-backend --no-pager || true
curl -s http://127.0.0.1:8000/api/health || echo "Backend not ready (set OPENAI_API_KEY in .env and: sudo systemctl restart crackthedeck-backend)"
echo ""
echo "Done. Site: http://$DOMAIN"
echo "Set OPENAI_API_KEY in $BACKEND_DIR/.env then: sudo systemctl restart crackthedeck-backend"
echo "Optional: to enable Find matching funds, run funds-rag (Docker) and set FUNDS_RAG_URL=http://127.0.0.1:8100 in .env"
