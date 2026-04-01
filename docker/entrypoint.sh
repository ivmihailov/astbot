#!/bin/sh
set -eu

mkdir -p /app/data /app/logs /app/storage/photos

if [ -z "${MAX_BOT_TOKEN:-}" ]; then
  echo "MAX_BOT_TOKEN is not set" >&2
  exit 1
fi

exec "$@"
