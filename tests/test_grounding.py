from scoutskit.grounding import corpus, ground_rows, value_grounded

PAGE = corpus("""
<table><tr><td>SIH26265</td><td>Streamline of security deposit/ FDR portal.</td><td>AICTE</td></tr>
<tr><td>SIH26264</td><td>Al-Enabled Drone &amp; Counter-Drone Threat Simulation Trainer</td><td>Ministry of Defence</td></tr></table>""")


def test_real_rows_are_accepted():
    rows = [{"id": "SIH26265", "title": "Streamline of security deposit/ FDR portal.", "org": "AICTE"}]
    good, bad = ground_rows(rows, PAGE, "id")
    assert good == rows and not bad


def test_invented_rows_are_rejected_with_a_reason():
    fake = {"id": "SIH26140", "title": "Quantum Key Distribution (QKD) Simulation Platform for Secure Data Transmission", "org": "Egreen Quanta"}
    good, bad = ground_rows([fake], PAGE, "id")
    assert not good and "not found on the page" in bad[0][1] and "SIH26140" in bad[0][1]


def test_a_missing_key_rejects_the_row_even_if_the_rest_is_real():
    good, bad = ground_rows([{"id": "SIH99999", "title": "Streamline of security deposit/ FDR portal.", "org": "AICTE"}], PAGE, "id")
    assert not good and bad


def test_a_small_typo_in_a_long_value_is_tolerated():
    # the site itself says "Al-Enabled" (a lowercase L); a model that reads it as "AI" is still grounded
    assert value_grounded("AI-Enabled Drone & Counter-Drone Threat Simulation Trainer", PAGE)


def test_entities_and_whitespace_do_not_matter():
    assert value_grounded("Al-Enabled   Drone & Counter-Drone Threat Simulation Trainer", PAGE)


def test_mixed_batches_keep_the_good_rows():
    real = {"id": "SIH26264", "title": "Al-Enabled Drone & Counter-Drone Threat Simulation Trainer", "org": "Ministry of Defence"}
    fake = {"id": "SIH11111", "title": "made up", "org": "nobody"}
    good, bad = ground_rows([real, fake], PAGE, "id")
    assert good == [real]
    assert [row["id"] for row, _ in bad] == ["SIH11111"]
