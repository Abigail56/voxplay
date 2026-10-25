#!/bin/sh
# One-time setup of a fresh Ubuntu server (Oracle Cloud Always Free, Ampere A1), then start VOXPLAY.
#   curl -fsSL https://raw.githubusercontent.com/Abigail56/voxplay/main/deploy/oracle/setup.sh | sh -s -- [domain]
# Without a domain it uses <public-ip>.sslip.io, which points at this server with no DNS setup.
# Run it again to update to the latest code.
set -e

DOMAIN="$1"
if [ -z "$DOMAIN" ]; then
  IP=$(curl -fsS https://api.ipify.org)
  DOMAIN="$(echo "$IP" | tr . -).sslip.io"
fi

# Docker
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

# Oracle's Ubuntu images block every port but 22 in iptables; open 80 and 443.
if ! sudo iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null; then
  sudo iptables -I INPUT 5 -p tcp --dport 80 -j ACCEPT
  sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
  sudo sh -c 'command -v netfilter-persistent >/dev/null && netfilter-persistent save' || true
fi

# The models and the site build need more than 1 GB; a swap file helps on small servers.
if [ ! -f /swapfile ] && [ "$(free -m | awk '/Mem:/ {print $2}')" -lt 4000 ]; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

# Code
if [ -d ~/voxplay ]; then
  git -C ~/voxplay pull --ff-only
else
  git clone https://github.com/Abigail56/voxplay.git ~/voxplay
fi
cd ~/voxplay

# Settings: a random JWT secret once, and the domain every time.
touch .env
grep -q '^JWT_SECRET=' .env || echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
sed -i '/^DOMAIN=/d' .env && echo "DOMAIN=$DOMAIN" >> .env

sudo docker compose -f docker-compose.yml -f deploy/oracle/docker-compose.prod.yml up -d --build

echo
echo "VOXPLAY is starting at https://$DOMAIN (the API loads its models for a minute or two)."
echo "Admin page: add ADMIN_USERNAMES=yourname to ~/voxplay/.env and run this script again."
