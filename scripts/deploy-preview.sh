#!/usr/bin/env bash
# Build the wiki and publish it to the preview host.
#
# The preview runs on sra-oracle behind the Cloudflare Tunnel that already
# serves shiny and koito there, so it stays up regardless of whether this
# laptop is on. That is the whole point: the project lead needs a link, not a
# VPN invite and a machine that has to stay awake.
#
#   scripts/deploy-preview.sh          build, then sync the build
#   scripts/deploy-preview.sh --setup  also push the compose stack and start it
#
# Dashboard routing is one-time and not scriptable: the tunnel is token-managed.

set -euo pipefail

HOST="${PREVIEW_HOST:-sra-oracle}"
REMOTE="${PREVIEW_DIR:-/home/ubuntu/discovery-preview}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "Building"
make build

if [[ "${1:-}" == "--setup" ]]; then
  say "Provisioning the preview stack on $HOST"
  ssh "$HOST" "mkdir -p $REMOTE/html $REMOTE/conf"
  rsync -az deploy/preview/docker-compose.yml "$HOST:$REMOTE/"
  rsync -az deploy/preview/nginx-preview.conf "$HOST:$REMOTE/conf/default.conf"
  # nginx-preview.conf includes this by absolute path; without it nginx refuses
  # to start and the container restart-loops instead of serving anything.
  rsync -az deploy/nginx-csp.conf "$HOST:$REMOTE/conf/"
  # compose v2 ships as a docker plugin here
  ssh "$HOST" "cd $REMOTE && sudo docker compose up -d"
fi

say "Syncing content"
rsync -az --delete astro/dist/ "$HOST:$REMOTE/html/"

say "Syncing nginx config"
rsync -az deploy/preview/nginx-preview.conf "$HOST:$REMOTE/conf/default.conf"
rsync -az deploy/nginx-csp.conf "$HOST:$REMOTE/conf/"

say "Reloading nginx"
# Config is bind-mounted, so a reload picks up header changes without downtime.
ssh "$HOST" "sudo docker exec eos-wiki nginx -s reload"

say "Checking the origin responds"
ssh "$HOST" '
code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8083/" || echo ---)
printf "  localhost:8083  ->  %s\n" "$code"'

cat <<'DONE'

Deployed. Public URL, once the tunnel hostname exists:

  https://eos-wiki.sradjoker.cc

If that 404s or hangs, the dashboard routing is not set up yet.
DONE
