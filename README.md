# basic_spine

Prototype of BASIC's money spine: **disbursement → MIS → matching → collection ledger**.

Ingests the console's reported-disbursement export and raw lender MIS files, normalizes
the broken join keys (zero-width Unicode, prefixes, separators, LAN-vs-AppId swaps),
matches them with a confidence waterfall (A / A− / B / C), and surfaces a collection /
leakage view. Payouts, invoicing, accounting and leads are **out of scope** for this
prototype.

## Install

```bash
bench get-app <this repo>
bench --site <site> install-app basic_spine
bench --site <site> migrate
```

Seed masters (products, lenders, entities, aliases, LAN patterns, MIS profiles):

```bash
bench --site <site> execute basic_spine.spine.setup.seed
```

## Data files

Put input files in `prototype_data/` under the bench's `sites/` directory — relative
paths in `bench execute` resolve there (absolute paths work too). The directory is
gitignored: real exports contain PII and must never be committed. To generate synthetic
fixture files that exercise every documented edge case (zero-width ids, backslashed
LANs, AU `L`/`HFT-` prefixes, drip-feed duplicate files, missing LANs):

```bash
bench --site <site> execute basic_spine.spine.make_fixtures.make_all --kwargs "{'out_dir':'prototype_data'}"
```

## Run order

```bash
# 1. Import the reported-disbursement export (Case Pipeline format, 2-row banner)
bench --site <site> execute basic_spine.spine.imports.import_reported \
  --kwargs "{'path':'prototype_data/reported.xlsx'}"

# 2. Import each lender MIS file against its Lender MIS Profile
bench --site <site> execute basic_spine.spine.imports.import_mis \
  --kwargs "{'path':'prototype_data/mis_chola.xlsx','profile':'Chola Monthly','received_on':'2026-04-20','mis_month':'Apr-26'}"
bench --site <site> execute basic_spine.spine.imports.import_mis \
  --kwargs "{'path':'prototype_data/mis_au_part1.xlsx','profile':'AU Monthly','received_on':'2026-04-18','mis_month':'Apr-26'}"
bench --site <site> execute basic_spine.spine.imports.import_mis \
  --kwargs "{'path':'prototype_data/mis_au_part2.xlsx','profile':'AU Monthly','received_on':'2026-04-21','mis_month':'Apr-26'}"

# 3. Run the matching waterfall
bench --site <site> execute basic_spine.spine.match.run_matching

# 4. Compute expected-in-MIS dates and overdue aging (also runs daily via scheduler)
bench --site <site> execute basic_spine.spine.aging.recompute_expected

# 5. End-to-end summary (definition-of-done numbers, incl. normalization-rescued count)
bench --site <site> execute basic_spine.spine.summary.print_summary

# Open the "Spine" workspace to view the four reports:
#   Collection Funnel · Leakage Aging · Match Quality · Claimed-post-MIS Monitor
```

## Notes / deviations from the spec

- `MIS Line` carries a `disb_date` field (and the column map supports a `DisbDate`
  target). The spec's field list omitted it, but the fuzzy-match rule (±7 days) and the
  line fingerprint both require it.
- `MIS Line.norm_rescued` flags matches that succeeded on normalized ids but would have
  failed on raw equality — the prototype's headline metric, reported in Match Quality.
- Leakage Aging estimates payin-at-risk as `disb_amt × 1%` — a clearly labelled
  placeholder until the Phase 2 rate engine exists.
