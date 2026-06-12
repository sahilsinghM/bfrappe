app_name = "basic_spine"
app_title = "Basic Spine"
app_publisher = "BASIC Home Loan"
app_description = "Disbursement -> MIS -> matching -> collection ledger spine (prototype)"
app_email = "sahilsingh7867@gmail.com"
app_license = "mit"

scheduler_events = {
    "daily": [
        "basic_spine.spine.aging.recompute_expected",
    ],
    "cron": {
        # Pull disbursements from the console API every 15 minutes.
        # Skips silently if spine_api_key is not configured.
        "*/15 * * * *": ["basic_spine.spine.sync.scheduled_pull"],
    },
}

# Route incoming Communications to the right email handler.
doc_events = {
    "Communication": {
        "after_insert": [
            "basic_spine.spine.mis_email_handler.process_incoming_email",
            "basic_spine.spine.disb_confirmation_handler.process_disbursement_email",
        ],
    },
}

fixtures = []
