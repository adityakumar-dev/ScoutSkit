import pytest

from scoutskit.browser.totals import stated_total


@pytest.mark.parametrize("text, expected", [
    ("Showing 1 to 25 of 265 entries", 265),
    ("Showing 26 to 50 of 1,234 entries", 1234),
    ("Show 25 entries ... Showing 1 to 3 of 3 entries (filtered from 265 total entries)", 3),  # the filtered size wins
    ("Displaying results 1-10 of 87 results", 87),
    ("312 results found", 312),
    ("Total records: 40", 40),
    ("Nothing to count here, 25 per page", None),
    ("", None),
])
def test_stated_total(text, expected):
    assert stated_total(text) == expected
