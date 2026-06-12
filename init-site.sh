#!/usr/bin/env bash
# One-time site creation. Run AFTER docker compose up -d and the backend
# is healthy. Safe to re-run — most bench commands are idempotent.
set -euo pipefail

# Load .env into the shell without polluting the environment permanently
set -a
# shellcheck disable=SC1091
source .env
set +a

bench_exec() {
    docker compose exec backend bench "$@"
}

echo "==> Creating site: $SITE_NAME"
bench_exec new-site \
    --db-root-password "$DB_ROOT_PASSWORD" \
    --admin-password  "$ADMIN_PASSWORD" \
    --install-app erpnext \
    "$SITE_NAME"

echo "==> Installing basic_spine"
bench_exec --site "$SITE_NAME" install-app basic_spine

echo "==> Enabling scheduler"
bench_exec --site "$SITE_NAME" enable-scheduler

echo "==> Seeding master data (products, lenders, MIS profiles…)"
bench_exec --site "$SITE_NAME" execute basic_spine.spine.setup.seed

echo ""
echo "Done. Open http://localhost:${HTTP_PORT:-8080} and log in as Administrator."
echo "Run ./run-pipeline.sh to generate fixtures and execute the full matching pipeline."
