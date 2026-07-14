#!/usr/bin/env bash
# Push AlphaFraud from your Mac to the droplet and restart the web service.
# Run from the repo root:  bash deploy/deploy.sh
#
# Reads DROPLET_SSH / DROPLET_PATH from .env (see .env.example). Idempotent; excludes the
# venv, cached data, the local DB and secrets so the server's state is never clobbered.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Load .env for DROPLET_SSH / DROPLET_PATH.
if [[ -f .env ]]; then set -a; source .env; set +a; fi
DROPLET_SSH="${DROPLET_SSH:-}"
DROPLET_PATH="${DROPLET_PATH:-/opt/alphafraud}"
SSH_KEY="${SSH_KEY:-}"

if [[ -z "$DROPLET_SSH" ]]; then
  echo "DROPLET_SSH is not set. Copy .env.example to .env and fill it in."; exit 1
fi

SSH_OPTS=()
[[ -n "$SSH_KEY" ]] && SSH_OPTS=(-e "ssh -i ${SSH_KEY/#\~/$HOME}")

echo "==> Syncing code to ${DROPLET_SSH}:${DROPLET_PATH}"
# ${arr[@]+"${arr[@]}"} expands to nothing when empty without tripping `set -u`
# (needed for macOS's bash 3.2, where "${arr[@]}" on an empty array is an error).
rsync -az --delete ${SSH_OPTS[@]+"${SSH_OPTS[@]}"} \
  --exclude '.venv/' --exclude 'data/' --exclude '__pycache__/' \
  --exclude '*.pyc' --exclude '.git/' --exclude '.env' \
  --exclude 'alphafraud.db' --exclude 'alphafraud.db-*' \
  ./ "${DROPLET_SSH}:${DROPLET_PATH}/"

echo "==> Installing dependencies + restarting service on the droplet"
SSH_CMD=(ssh)
[[ -n "$SSH_KEY" ]] && SSH_CMD=(ssh -i "${SSH_KEY/#\~/$HOME}")
"${SSH_CMD[@]}" "$DROPLET_SSH" bash -s <<REMOTE
set -euo pipefail
cd "${DROPLET_PATH}"
if [[ ! -x .venv/bin/python ]]; then
  echo "No venv yet -- run deploy/provision.sh as root first."; exit 0
fi
sudo -u alphafraud ./.venv/bin/pip install --quiet -r requirements.txt
sudo chown -R alphafraud:alphafraud "${DROPLET_PATH}"
sudo systemctl restart alphafraud-web.service
sudo systemctl --no-pager --lines=2 status alphafraud-web.service || true
REMOTE

echo "==> Deployed."
