"""Demo tasks for the STROT Space.

Each task is a self-contained decision problem: a query, a bounded action
registry, a per-record question, and a small sample used to compile the
artifact. The same definitions drive both pre-compilation (build time) and the
live "Try it" tab (runtime), so the cache key matches and runtime stays
key-free.
"""

TASKS = {
    "support": {
        "label": "Support ticket triage",
        "query": "Triage incoming support tickets into the correct workflow.",
        "question": "Which workflow should handle this ticket?",
        "registry": {
            "billing_dispute":  "Refunds, invoice corrections, double charges, billing questions.",
            "technical_defect": "Crashes, bugs, errors, broken or unexpected behavior.",
            "account_access":   "Login problems, password resets, locked or suspended accounts.",
        },
        "examples": [
            "I was charged twice for the same subscription this month, please refund one.",
            "The app crashes every time I open the reports page on Android.",
            "I can't log in, it says my account is locked after too many attempts.",
            "My invoice shows the wrong tax amount for my region.",
            "Export to CSV produces an empty file since yesterday's update.",
        ],
    },
    "finance": {
        "label": "Consumer complaint → product",
        "query": "Route each consumer-finance complaint to the product it concerns.",
        "question": "Which financial product is this complaint about?",
        "registry": {
            "credit_reporting": "A dispute about a credit report, credit score, or a credit bureau: wrong info, inquiries, identity theft on the report.",
            "debt_collection":  "A complaint about a debt collector: collection calls, a debt not owed, harassment, validation of a debt.",
            "credit_card":      "A complaint about a credit card: fees, interest, rewards, billing disputes, closed accounts.",
            "bank_account":     "A complaint about a checking/savings account: deposits, overdrafts, holds, closures, fraud on the account.",
            "mortgage":         "A complaint about a mortgage or home loan: servicing, escrow, modification, foreclosure, payments.",
            "money_transfer":   "A complaint about a money transfer, wire, remittance, or digital wallet.",
        },
        "examples": [
            "There is a hard inquiry on my Experian report that I never authorized.",
            "A collection agency keeps calling about a debt I already paid off two years ago.",
            "My credit card issuer charged a late fee even though I paid before the due date.",
            "The bank placed a 10-day hold on my check deposit with no explanation.",
            "My mortgage servicer misapplied my escrow and now says I'm behind on payments.",
            "I sent a wire transfer that never arrived and support won't trace it.",
        ],
    },
}
