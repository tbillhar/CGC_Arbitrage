from pathlib import Path

import pytest

from config import EbayConfig
from ebay_client import EbayApiError, EbayClient, EbayCredentialsMissingError


def test_live_mode_without_credentials_raises_clear_error() -> None:
    client = EbayClient(EbayConfig(mode="live", client_id="", client_secret=""))

    with pytest.raises(EbayCredentialsMissingError, match="credentials are not configured"):
        client.search_active_listings("Amazing Spider-Man", "300", 8.0, 9.8)


def test_mock_mode_reads_matching_listings(tmp_path: Path) -> None:
    mock_file = tmp_path / "mock_ebay_listings.csv"
    mock_file.write_text(
        "item_id,watch_title,watch_issue_number,title,price,currency,item_url,seller_username\n"
        "1,Amazing Spider-Man,300,Amazing Spider-Man #300 CGC 9.8 White Pages,4000,USD,https://example.test/1,seller\n"
        "2,New Mutants,98,New Mutants #98 CGC 9.8 White Pages,475,USD,https://example.test/2,seller\n",
        encoding="utf-8",
    )
    client = EbayClient(EbayConfig(mode="mock", mock_listings_path=mock_file))

    listings = client.search_active_listings("Amazing Spider-Man", "300", 8.0, 9.8)

    assert len(listings) == 1
    assert listings[0].item_id == "1"
    assert listings[0].price == 4000


def test_mock_mode_reports_bad_price(tmp_path: Path) -> None:
    mock_file = tmp_path / "mock_ebay_listings.csv"
    mock_file.write_text(
        "item_id,watch_title,watch_issue_number,title,price,currency,item_url,seller_username\n"
        "1,Amazing Spider-Man,300,Amazing Spider-Man #300 CGC 9.8 White Pages,not-a-price,USD,https://example.test/1,seller\n",
        encoding="utf-8",
    )
    client = EbayClient(EbayConfig(mode="mock", mock_listings_path=mock_file))

    with pytest.raises(EbayApiError, match="invalid price"):
        client.search_active_listings("Amazing Spider-Man", "300", 8.0, 9.8)
