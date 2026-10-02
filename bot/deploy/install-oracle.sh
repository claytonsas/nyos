#!/usr/bin/env bash
# Installation sur une VM Oracle Cloud "Always Free" (Ubuntu 22.04/24.04, ARM ou x86).
# Usage, depuis le dossier bot/ copié sur la VM :  sudo bash deploy/install-oracle.sh
set -euo pipefail

APP=/opt/nyos-bot

apt-get update
apt-get install -y python3 python3-venv ufw unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades

id bot >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin bot
mkdir -p "$APP/data"
cp -r trader requirements.txt "$APP/"
[ -f "$APP/config.yaml" ] || cp config.example.yaml "$APP/config.yaml"
[ -f "$APP/.env" ] || cp .env.example "$APP/.env"
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install --upgrade pip
"$APP/.venv/bin/pip" install -r "$APP/requirements.txt"
chown -R bot:bot "$APP"
chmod 600 "$APP/.env"

# Pare-feu : SSH uniquement, le bot n'a besoin d'aucun port entrant.
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable

cp deploy/nyos-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable nyos-bot

echo
echo "Installé. Étapes suivantes :"
echo "  1. sudo nano $APP/config.yaml   (mode: paper pour commencer)"
echo "  2. sudo nano $APP/.env          (Telegram, puis clés API plus tard)"
echo "  3. sudo systemctl start nyos-bot"
echo "  4. journalctl -u nyos-bot -f    (voir les logs)"
