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
# --chmod: every file in the Mac's iCloud-synced tree is mode 600 and its directories
# 700, and plain -a carries that straight onto the droplet. On 2026-11-17 it did: it set
# /opt/alphafraud to drwx------ dellboy:staff, the alphafraud user could no longer traverse
# its own code, the site served 500, and the pip line below then failed with "Permission
# denied" -- which under `set -e` skipped the chown that would have repaired it. Forcing the
# modes here means the deploy no longer depends on that repair to leave a working app.
rsync -az --delete --chmod=F644,D755 ${SSH_OPTS[@]+"${SSH_OPTS[@]}"} \
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
# rsync (run as root) leaves new code files root-owned; chown them to alphafraud, but
# PRUNE data/, the venv and the live DB so we never touch the database a running backfill
# has open (a blanket chown -R over the open DB likely caused a mid-run "readonly" crash).
#
# This runs BEFORE pip, not after. It used to come later, which made the deploy depend on
# a step that itself needed the repair: once rsync had left the tree unreadable to the
# alphafraud user, the `sudo -u alphafraud` pip line below died with "Permission denied"
# and `set -e` aborted the script before this block could fix anything. Ownership first,
# then anything that runs as that user.
sudo find "${DROPLET_PATH}" \
  -path "${DROPLET_PATH}/data" -prune -o \
  -path "${DROPLET_PATH}/.venv" -prune -o \
  -name 'alphafraud.db*' -prune -o \
  -exec chown alphafraud:alphafraud {} +
# PIP_NO_CACHE_DIR silences pip's warning about the root-owned ~/.cache/pip under the
# alphafraud user (the cache buys nothing here -- deps are already installed after the
# first provision, so reinstalls are near-instant regardless).
sudo -u alphafraud env PIP_NO_CACHE_DIR=1 ./.venv/bin/pip install --quiet -r requirements.txt
sudo systemctl restart alphafraud-web.service
sudo systemctl --no-pager --lines=2 status alphafraud-web.service || true
REMOTE

echo "==> Deployed."
