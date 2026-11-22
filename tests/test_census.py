from scoutskit.browser.census import Census, compare, tables


def page(rows: int, table_id: str = "t", prefix: str = "SIH") -> str:
    body = "".join(f"<tr><td>{prefix}{26000 + i}</td><td>Title {i}</td></tr>" for i in range(rows))
    return f"<html><body><table id='{table_id}'><thead><tr><th>ID</th></tr></thead><tbody>{body}</tbody></table></body></html>"


def test_a_paged_table_shows_fewer_rows_than_the_source_holds():
    census = compare(tables(page(265), with_text=True), tables(page(25)))
    assert census == Census("table#t", 265, 25)
    assert "holds 265 rows in table#t" in census.sentence() and "shows only 25" in census.sentence()


def test_a_table_that_shows_everything_has_no_census():
    assert compare(tables(page(40), with_text=True), tables(page(40))) is None


def test_small_tables_are_ignored():
    assert compare(tables(page(5), with_text=True), tables(page(1))) is None


def test_rows_of_nested_tables_are_not_counted_for_the_outer_table():
    inner = "<table><tbody>" + "<tr><td>x</td></tr>" * 20 + "</tbody></table>"
    outer = "<table id='outer'><tbody>" + f"<tr><td>{inner}</td></tr>" * 3 + "</tbody></table>"
    counted = {table.selector: table.rows for table in tables(outer)}
    assert counted["table#outer"] == 3


def test_the_table_the_agents_rows_came_from_is_chosen_over_a_bigger_unrelated_one():
    raw = tables(page(300, "other", "ZZZ") .replace("</body>", page(120, "mine").split("<body>")[1]), with_text=True)
    census = compare(raw, [], keys=["sih26005"])
    assert census.selector == "table#mine" and census.raw_rows == 120


def test_a_source_that_cannot_be_parsed_has_no_tables():
    assert tables("") == []


from scoutskit.browser.census import detail_blocks  # noqa: E402


def item_page(count: int, in_thead: bool = False, nested: bool = True, omit_last_label: bool = False, data_tables: bool = False) -> str:
    def block(i: int) -> str:
        if data_tables:  # a repeated small table of ordinary 3-column data rows
            return "<table id='d'><thead><tr><th>A</th><th>B</th><th>C</th></tr></thead><tbody>" + f"<tr><td>{i}</td><td>b</td><td>c</td></tr>" * 3 + "</tbody></table>"
        last = "" if omit_last_label and i == 0 else f"<tr><th>Note</th><td>n{i}</td></tr>"
        body = f"<tr><th>Name</th><td>x{i}</td></tr><tr><th>Owner</th><td>o{i}</td></tr>{last}"
        return f"<table id='d'>{'<thead>' + body + '</thead>' if in_thead else body}</table>"

    rows = "".join(f"<tr><td>{i}</td><td>{block(i) if nested else ''}</td></tr>" for i in range(count))
    loose = "" if nested else "".join(block(i) for i in range(count))
    return f"<html><body><table id='main'><tbody>{rows}</tbody></table>{loose}</body></html>"


def test_repeated_label_value_blocks_inside_rows_are_found_with_their_fields():
    (blocks,) = detail_blocks(item_page(12))
    assert (blocks.selector, blocks.count, blocks.labels, blocks.host) == ("table#d", 12, ("Name", "Owner", "Note"), "table#main")
    assert "one inside each row of table#main" in blocks.sentence() and "Name | Owner | Note" in blocks.sentence()


def test_blocks_outside_the_rows_are_reported_as_elsewhere():
    (blocks,) = detail_blocks(item_page(12, nested=False))
    assert blocks.host == "" and "elsewhere on the page" in blocks.sentence()


def test_a_field_missing_from_some_blocks_is_still_listed():
    (blocks,) = detail_blocks(item_page(12, omit_last_label=True))
    assert "Note" in blocks.labels  # the first block lacks it, the others have it


def test_too_few_blocks_are_not_a_pattern():
    assert detail_blocks(item_page(3)) == []


def test_label_value_rows_inside_a_thead_are_found_as_on_the_real_sih_page():
    (blocks,) = detail_blocks(item_page(12, in_thead=True))
    assert blocks.labels == ("Name", "Owner", "Note") and blocks.host == "table#main"


def test_repeated_ordinary_data_tables_are_not_detail_blocks():
    assert detail_blocks(item_page(12, data_tables=True)) == []


def test_pages_without_such_blocks_report_nothing():
    assert detail_blocks(page(40)) == [] and detail_blocks("") == []
