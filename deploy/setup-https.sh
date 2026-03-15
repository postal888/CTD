#!/bin/bash
# Run ON the server to get Let's Encrypt SSL for the site.
# Prerequisites: domain DNS A record points to this server; ports 80 and 443 open.
#
# Usage:
#   ./setup-https.sh yourdomain.com
#   ./setup-https.sh yourdomain.com you@email.com   # email for Let's Encrypt
#
set -e
DOMAIN="${1:?Usage: $0 DOMAIN [EMAIL]}"
EMAIL="${2:-}"

echo "=== Installing certbot (if needed) ==="
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx >/dev/null 2>&1 || true

echo "=== Set server_name to $DOMAIN in Nginx ==="
NGINX_CONF="/etc/nginx/sites-available/crackthedeck"
sudo sed -i "s/server_name .*;/server_name $DOMAIN _;/" "$NGINX_CONF"
sudo nginx -t && sudo systemctl reload nginx

echo "=== Getting certificate from Let's Encrypt ==="
if [ -n "$EMAIL" ]; then
  sudo certbot --nginx -d "$DOMAIN" --redirect --non-interactive --agree-tos --email "$EMAIL"
else
  sudo certbot --nginx -d "$DOMAIN" --redirect
fi

echo "=== Done. Site should be available at https://$DOMAIN ==="
