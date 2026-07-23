from openbankingmcp.reporting import summarise


def test_summary_includes_pending_spend_and_labels_the_breakdown():
    result=summarise([
        {"amount_minor":-1000,"category":"dining","status":"booked"},
        {"amount_minor":-725,"category":"dining","status":"pending"},
        {"amount_minor":500,"category":"uncategorised","status":"pending"},
    ])

    assert result["spending_minor"] == 1725
    assert result["booked_spending_minor"] == 1000
    assert result["pending_spending_minor"] == 725
    assert result["pending_transaction_count"] == 2
