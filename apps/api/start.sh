#!/bin/sh
# Container entrypoint: migrate, seed an empty database (if SEED_ON_START=true), serve.
set -e
alembic upgrade head
python -m app.bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
