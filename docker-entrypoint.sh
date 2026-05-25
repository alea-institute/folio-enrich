#!/bin/sh
# Entrypoint for the folio-enrich container image (used by Railway).
#
# A Railway persistent volume is mounted at ~/.folio-enrich (to cache the embedding
# index across restarts/deploys). Railway mounts volumes root-owned, but the app runs
# as the non-root `appuser`, so we run this entrypoint as root to fix ownership, then
# drop privileges to appuser via gosu.
set -e

CACHE_HOME="/home/appuser/.folio-enrich"
mkdir -p "$CACHE_HOME/cache/embeddings" "$CACHE_HOME/jobs"
chown -R appuser:appuser "$CACHE_HOME"

exec gosu appuser "$@"
