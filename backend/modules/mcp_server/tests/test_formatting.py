from datetime import UTC, datetime

from mcp_server.formatting import format_inr, format_when


def test_indian_digit_grouping() -> None:
    assert format_inr(8245000) == "₹82,450.00"
    assert format_inr(15632050) == "₹1,56,320.50"
    assert format_inr(199900) == "₹1,999.00"
    assert format_inr(5) == "₹0.05"
    assert format_inr(1234567890) == "₹1,23,45,678.90"
    assert format_inr(-199900) == "-₹1,999.00"


def test_times_are_shown_in_ist() -> None:
    assert format_when(datetime(2026, 9, 25, 15, 43, tzinfo=UTC)) == "Fri 25 Sep 2026, 21:13 IST"
