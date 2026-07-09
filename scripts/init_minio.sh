#!/bin/sh
set -eu

host="http://minio:9000"
user="${MINIO_ROOT_USER:-ragforge}"
password="${MINIO_ROOT_PASSWORD:-ragforge123}"

attempt=0
until mc alias set local "$host" "$user" "$password" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "MinIO is not ready after 30 attempts" >&2
    exit 1
  fi
  sleep 2
done

mc mb -p local/bronze >/dev/null 2>&1 || true
mc mb -p local/silver >/dev/null 2>&1 || true
mc mb -p local/gold >/dev/null 2>&1 || true

echo "MinIO buckets created: bronze, silver, gold"
