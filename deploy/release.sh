#!/usr/bin/env bash
# One-shot release: commit + push to GitHub, then deploy to the droplet.
#
#   bash deploy/release.sh "commit message"
#
# Skips the commit step cleanly if there is nothing staged/changed (lets you re-deploy
# the current HEAD). Deploy always runs, so `release.sh` with no new changes just
# re-pushes the running code -- handy after a manual git commit.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MSG="${1:-}"

# --- 1. commit (only if there is something to commit) ---
if [[ -n "$(git status --porcelain)" ]]; then
  if [[ -z "$MSG" ]]; then
    echo "There are uncommitted changes but no commit message given."
    echo "Usage: bash deploy/release.sh \"your commit message\""
    exit 1
  fi
  echo "==> Committing"
  git add -A
  git commit -q -m "$MSG"
else
  echo "==> No changes to commit (deploying current HEAD)"
fi

# --- 2. push to GitHub ---
echo "==> Pushing to GitHub"
git push -q

# --- 3. deploy to the droplet ---
echo "==> Deploying to the droplet"
bash "$REPO_ROOT/deploy/deploy.sh"

echo "==> Release complete: $(git rev-parse --short HEAD) is on GitHub and live."
