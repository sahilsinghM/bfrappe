#!/usr/bin/env bash
# End-to-end prototype pipeline:
#   generate synthetic fixtures → import → match → age → summary
#
# prototype_data/ is written to the sites volume so it persists across restarts.
# To use real BASIC exports instead of synthetic fixtures, copy them into the
# sites volume first:
#   docker compose cp /path/to/reported.xlsx backend:/home/frappe/frappe-bench/sites/prototype_data/
# then comment out the make_fixtures step below.
set -euo pipefail

set -a
# shellcheck disable=SC1091
source .env
set +a

SITE="$SITE_NAME"

be() {
    docker compose exec backend bench --site "$SITE" execute "$@"
}

echo "==> Generating synthetic fixture files into sites/prototype_data/"
be basic_spine.spine.make_fixtures.make_all \
    --kwargs "{'out_dir':'sites/prototype_data'}"

echo "==> Importing reported disbursements"
be basic_spine.spine.imports.import_reported \
    --kwargs "{'path':'sites/prototype_data/reported.xlsx'}"

echo "==> Importing Chola MIS (Apr-26)"
be basic_spine.spine.imports.import_mis \
    --kwargs "{'path':'sites/prototype_data/mis_chola.xlsx','profile':'Chola Monthly','received_on':'2026-04-20','mis_month':'Apr-26'}"

echo "==> Importing AU MIS part 1 (Apr-26, drip-feed)"
be basic_spine.spine.imports.import_mis \
    --kwargs "{'path':'sites/prototype_data/mis_au_part1.xlsx','profile':'AU Monthly','received_on':'2026-04-18','mis_month':'Apr-26'}"

echo "==> Importing AU MIS part 2 (3 rows overlap with part 1 — deduped by fingerprint)"
be basic_spine.spine.imports.import_mis \
    --kwargs "{'path':'sites/prototype_data/mis_au_part2.xlsx','profile':'AU Monthly','received_on':'2026-04-21','mis_month':'Apr-26'}"

echo "==> Running matching waterfall (A → A− → B → C)"
be basic_spine.spine.match.run_matching

echo "==> Computing expected-in-MIS dates and overdue aging"
be basic_spine.spine.aging.recompute_expected

echo "==> End-to-end summary (definition-of-done numbers)"
be basic_spine.spine.summary.print_summary
