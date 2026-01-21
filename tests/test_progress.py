from tools import progress


def test_normalize_progress_log_dedupes_and_archives():
    lines = [
        "- 2024-01-01 source=implement id=I1 kind=iteration hash=abc link=aidd/reports/tests/t.log msg=done",
        "- 2024-01-01 source=implement id=I1 kind=iteration hash=abc link=aidd/reports/tests/t.log msg=done",
        "- 2024-01-02 source=implement id=I2 kind=iteration hash=def link=aidd/reports/tests/t.log msg=ok",
    ]
    normalized, archived, summary = progress.normalize_progress_log(lines, max_lines=1)
    assert len(normalized) == 1
    assert len(archived) == 1
    assert "archived=1" in ",".join(summary)


def test_parse_progress_log_lines_skips_empty_marker():
    entries, invalid = progress.parse_progress_log_lines(["- (empty)", "- invalid entry"])
    assert entries == []
    assert len(invalid) == 1
