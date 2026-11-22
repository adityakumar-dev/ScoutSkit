"""Which field identifies a row, when the page has a serial-number column it leaves empty."""

from scoutskit.tools.collector import Collector


def test_an_empty_serial_column_does_not_reject_real_rows():
    rows = [{"sl_no": "", "name": "B.Tech (CSE)", "file": "BTech_CSE.pdf"}, {"sl_no": "", "name": "B.Tech (IT)", "file": "BTech_IT.pdf"}]
    collector = Collector([])
    assert collector.add(rows) == (2, 0, 0)
    assert collector.key_field == "name"


def test_a_row_without_its_key_is_kept_by_its_other_values_and_an_empty_row_is_not():
    collector = Collector(["code", "name"], "code")
    assert collector.add([{"code": "A1", "name": "x"}, {"code": "", "name": "y"}, {"code": "", "name": "y"}, {"code": "", "name": ""}]) == (2, 1, 1)
