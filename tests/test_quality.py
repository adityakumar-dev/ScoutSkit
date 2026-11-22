from scoutskit.quality import quality_warnings


def clean(n: int = 20) -> list[dict]:
    return [{"title": f"Streamline of security deposit portal {i}", "org": "AICTE", "category": "software", "theme": "Smart Automation"} for i in range(n)]


def test_clean_rows_have_no_warnings():
    assert quality_warnings(clean()) == []


def test_a_title_that_swallowed_the_detail_block_is_flagged_with_the_cause():
    rows = [
        {**row, "title": f"{row['title']} Problem Statement ID {i} Organization {row['org']} Category {row['category']} Theme {row['theme']} Description about {i}"}
        for i, row in enumerate(clean())
    ]
    (warning,) = quality_warnings(rows)
    assert "column 'title' looks polluted" in warning and "in 20 of 20 rows" in warning
    assert "hidden modal or detail block" in warning


def test_a_long_description_that_mentions_one_other_value_is_not_flagged():
    rows = [{"title": f"Item {i}", "category": "software", "description": "A long free-text description. " * 5 + "It mentions software once."} for i in range(20)]
    assert quality_warnings(rows) == []


def test_pollution_in_only_a_few_rows_is_tolerated():
    rows = clean(20)
    rows[0]["title"] += " Organization AICTE Category software Theme Smart Automation and more text to be long enough"
    assert quality_warnings(rows) == []


def test_a_huge_value_is_flagged():
    rows = clean(5)
    rows[2]["title"] = "x" * 6_000
    (warning,) = quality_warnings(rows)
    assert "'title' has a value of 6,000 characters" in warning
