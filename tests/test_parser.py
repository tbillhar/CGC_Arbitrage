from parser import DEAL_BREAKER_FLAGS, parse_listing_title


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


def test_parse_issue_without_hash_and_page_alias() -> None:
    parsed = parse_listing_title("ASM 300 CGC 9.8 WP")

    assert parsed.issue_number == "300"
    assert parsed.grade == 9.8
    assert parsed.page_quality == "White Pages"


def test_parse_grade_before_title_and_issue() -> None:
    parsed = parse_listing_title("CGC 9.8 Amazing Spider-Man #300 White Pages")

    assert parsed.issue_number == "300"
    assert parsed.grade == 9.8
    assert parsed.grading_company == "CGC"


def test_parse_signature_series_and_listing_flags() -> None:
    parsed = parse_listing_title("ASM #300 CGC SS NM/MT 9.8 Newsstand 1st Venom")

    assert parsed.issue_number == "300"
    assert parsed.grade == 9.8
    assert "signature_series" in parsed.flags
    assert "newsstand" in parsed.flags
    assert "first_appearance" in parsed.flags


def test_parse_canadian_price_variant_flag() -> None:
    parsed = parse_listing_title("Amazing Spider-Man 252 CGC 9.6 Canadian Price Variant")

    assert parsed.issue_number == "252"
    assert parsed.grade == 9.6
    assert "canadian_price_variant" in parsed.flags


def test_parse_qualified_and_missing_mvs_flags() -> None:
    parsed = parse_listing_title("Incredible Hulk #181 CGC 8.0 Qualified Missing MVS")

    assert parsed.issue_number == "181"
    assert parsed.grade == 8.0
    assert "qualified" in parsed.flags
    assert "missing_mvs" in parsed.flags
    assert DEAL_BREAKER_FLAGS.intersection(parsed.flags)


def test_issue_number_is_not_parsed_as_integer_grade() -> None:
    parsed = parse_listing_title("Avengers & X-Men: Axis #5 CBCS NOT CGC 9.8 Johnson Cover Marvel Comics 2015")

    assert parsed.issue_number == "5"
    assert parsed.grade == 9.8
    assert "not_cgc" in parsed.flags
    assert "modern_year" in parsed.flags
    assert DEAL_BREAKER_FLAGS.intersection(parsed.flags)


def test_modern_year_is_flagged_for_vintage_watchlist_filtering() -> None:
    parsed = parse_listing_title("2023 Fleer Ultra Wolverine Team Affiliations Blue Foil New Avengers CGC 8")

    assert parsed.grade == 8.0
    assert "modern_year" in parsed.flags
    assert DEAL_BREAKER_FLAGS.intersection(parsed.flags)


def test_later_volume_reprint_and_annual_flags_are_deal_breakers() -> None:
    parsed = parse_listing_title("Iron Man V2 #1 CGC 7.0 Special Edition")

    assert parsed.issue_number == "1"
    assert parsed.grade == 7.0
    assert "later_volume" in parsed.flags
    assert "reprint" in parsed.flags
    assert DEAL_BREAKER_FLAGS.intersection(parsed.flags)
