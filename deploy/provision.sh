#!/usr/bin/env bash
# One-time droplet provisioning for AlphaFraud. Run as root ON the droplet, AFTER the code
# is present at /opt/alphafraud (push it first with deploy/deploy.sh from your Mac, or
# `git clone` into /opt/alphafraud).
#
#   sudo SERVER_NAME=alphafraud.mdeller.com bash /opt/alphafraud/deploy/provision.sh
#
# Idempotent: safe to re-run. Installs system packages, a service user, the Python venv,
# the systemd web service + weekly timer, the nginx site, and a Let's Encrypt certificate.
set -euo pipefail

APP_DIR=/opt/alphafraud
APP_USER=alphafraud
BIND_ADDR="${BIND_ADDR:-127.0.0.1:8000}"

# Pull SERVER_NAME/BIND_ADDR from .env if not passed in the environment.
if [[ -f "$APP_DIR/.env" ]]; then
  set -a; # shellcheck disable=SC1091
  source "$APP_DIR/.env"; set +a
fi
SERVER_NAME="${SERVER_NAME:-alphafraud.mdeller.com}"

echo "==> AlphaFraud provisioning for ${SERVER_NAME}"

if [[ $EUID -ne 0 ]]; then echo "Run as root (sudo)."; exit 1; fi
if [[ ! -f "$APP_DIR/AlphaFraud.py" ]]; then
  echo "No code at $APP_DIR. Push it first: bash deploy/deploy.sh (from your Mac)."; exit 1
fi

echo "==> Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip python3-dev build-essential \
  nginx certbot python3-certbot-nginx rsync

echo "==> Creating service user '${APP_USER}'"
id -u "$APP_USER" &>/dev/null || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR/data"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> Building Python venv"
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
fi
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "==> Initializing app (dirs, DB schema, vendored plotly.js)"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/AlphaFraud.py" init

echo "==> Installing systemd units"
cp "$APP_DIR/deploy/alphafraud-web.service"      /etc/systemd/system/
cp "$APP_DIR/deploy/alphafraud-run.service"      /etc/systemd/system/
cp "$APP_DIR/deploy/alphafraud-run.timer"        /etc/systemd/system/
cp "$APP_DIR/deploy/alphafraud-backfill.service" /etc/systemd/system/
cp "$APP_DIR/deploy/alphafraud-analyze.service"  /etc/systemd/system/
cp "$APP_DIR/deploy/alphafraud-analyze.timer"    /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now alphafraud-web.service
systemctl enable --now alphafraud-run.timer
systemctl enable --now alphafraud-analyze.timer
# alphafraud-backfill is installed but NOT enabled -- the full-archive fill is a deliberate,
# one-time action. Start it with: systemctl enable --now alphafraud-backfill

echo "==> Installing nginx site"
sed -e "s|__SERVER_NAME__|${SERVER_NAME}|g" -e "s|__BIND_ADDR__|${BIND_ADDR}|g" \
  "$APP_DIR/deploy/nginx-alphafraud.conf" > /etc/nginx/sites-available/alphafraud
ln -sf /etc/nginx/sites-available/alphafraud /etc/nginx/sites-enabled/alphafraud
nginx -t && systemctl reload nginx

echo "==> Requesting TLS certificate (certbot)"
if certbot certificates 2>/dev/null | grep -q "$SERVER_NAME"; then
  echo "    Certificate for ${SERVER_NAME} already present; skipping."
else
  certbot --nginx -d "$SERVER_NAME" --non-interactive --agree-tos \
    -m "${CERTBOT_EMAIL:-marc@marcdeller.com}" --redirect || \
    echo "    certbot failed (DNS not pointed yet?). Re-run: certbot --nginx -d ${SERVER_NAME}"
fi

echo "==> Done. Status:"
systemctl --no-pager --lines=3 status alphafraud-web || true
echo "    Site:   https://${SERVER_NAME}/"
echo "    Timer:  $(systemctl list-timers alphafraud-run.timer --no-pager | sed -n 2p)"
echo "    First run now (optional):  systemctl start alphafraud-run.service"
