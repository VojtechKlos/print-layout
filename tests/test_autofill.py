from printlayout.autofill import autofill, reflow


def test_ten_photos_in_two_by_two_make_three_sheets():
    ids = [f"p{i}" for i in range(10)]
    sheets = autofill(ids, 4)
    assert sheets == [
        ["p0", "p1", "p2", "p3"],
        ["p4", "p5", "p6", "p7"],
        ["p8", "p9", None, None],
    ]


def test_exact_fit_has_no_extra_sheet():
    assert len(autofill(["a", "b", "c", "d"], 4)) == 1


def test_no_photos_gives_one_empty_sheet():
    assert autofill([], 4) == [[None, None, None, None]]


def test_reflow_keeps_sheets_and_moves_overflow_after_them():
    sheets = [["a", None, "b", "c"], [None, None, None, None], ["d", None, None, None]]
    assert reflow(sheets, 2) == [["a", "b"], ["c", None], [None, None], ["d", None]]


def test_reflow_to_bigger_grid_compacts():
    assert reflow([[None, "a", None, "b"]], 9) == [["a", "b"] + [None] * 7]
