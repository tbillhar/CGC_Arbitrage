from parser import parse_listing_title


def test_parse_cgc_grade_issue_and_white_pages() -> None:
    parsed = parse_listing_title("Amazing Spider-Man #300 CGC 9.8 White Pages")

    assert parsed.issue_number == "300"
    assert parsed.grade == 9.8
    assert parsed.page_quality == "White Pages"
    assert parsed.grading_company == "CGC"


def test_parse_common_page_quality_alias() -> None:
    parsed = parse_listing_title("New Mutants #98 CGC 9.6 OWW")

    assert parsed.issue_number == "98"
    assert parsed.grade == 9.6
    assert parsed.page_quality == "Off-White to White Pages"


def test_raw_listing_without_slab_grade_is_not_parsed_as_cgc() -> None:
    parsed = parse_listing_title("Amazing Spider-Man #300 raw high grade unread")

    assert parsed.issue_number == "300"
    assert parsed.grade is None
    assert parsed.grading_company is None
