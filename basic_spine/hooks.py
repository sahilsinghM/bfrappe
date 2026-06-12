app_name = "basic_spine"
app_title = "Basic Spine"
app_publisher = "BASIC Home Loan"
app_description = "Disbursement -> MIS -> matching -> collection ledger spine (prototype)"
app_email = "sahilsingh7867@gmail.com"
app_license = "mit"

# Daily recompute of expected-in-MIS dates and overdue flags.
# Also runnable on demand:
#   bench --site <site> execute basic_spine.spine.aging.recompute_expected
scheduler_events = {
    "daily": [
        "basic_spine.spine.aging.recompute_expected",
    ],
}

fixtures = []
