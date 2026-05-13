from pathlib import Path
from urllib.error import URLError

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


def test_item_summary_uses_current_bid_price_when_price_is_absent() -> None:
    client = EbayClient(EbayConfig(mode="mock"))

    listings = list(
        client._parse_item_summaries(
            [
                {
                    "itemId": "auction-1",
                    "title": "Amazing Spider-Man #300 CGC 9.8 White Pages",
                    "currentBidPrice": {"value": "1275.50", "currency": "USD"},
                    "itemWebUrl": "https://example.test/auction-1",
                    "seller": {"username": "auction_seller"},
                }
            ]
        )
    )

    assert listings[0].price == 1275.50
    assert listings[0].currency == "USD"
    assert listings[0].buying_options == ("AUCTION",)
    assert listings[0].is_fixed_price is False


def test_search_active_listings_requests_fixed_price_only(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EbayClient(EbayConfig(mode="live", client_id="id", client_secret="secret"))
    requested_urls: list[str] = []

    def fake_get_json(url: str) -> dict[str, object]:
        requested_urls.append(url)
        return {"itemSummaries": []}

    monkeypatch.setattr(client, "_get_json", fake_get_json)

    client.search_active_listings("X-Men", "4", 5.0, 8.0)

    assert "buyingOptions%3A%7BFIXED_PRICE%7D" in requested_urls[0]


def test_item_summary_extracts_item_specifics() -> None:
    client = EbayClient(EbayConfig(mode="mock"))

    listings = list(
        client._parse_item_summaries(
            [
                {
                    "itemId": "modern-1",
                    "title": "X-men 4 Cgc 5.0",
                    "price": {"value": "100", "currency": "USD"},
                    "buyingOptions": ["FIXED_PRICE"],
                    "itemWebUrl": "https://example.test/modern-1",
                    "seller": {"username": "seller"},
                    "additionalItemProperties": [
                        {"name": "Era", "value": "Modern Age (1992-Now)"},
                        {"name": "Publication Year", "value": "1992"},
                    ],
                }
            ]
        )
    )

    assert listings[0].is_fixed_price is True
    assert listings[0].item_specifics == {
        "era": "Modern Age (1992-Now)",
        "publication year": "1992",
    }


def test_request_json_retries_transient_url_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EbayClient(EbayConfig(mode="mock"))
    calls = 0

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(*args: object, **kwargs: object) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise URLError("connection reset")
        return FakeResponse()

    monkeypatch.setattr("ebay_client.urlopen", fake_urlopen)
    monkeypatch.setattr("ebay_client.time.sleep", lambda seconds: None)

    assert client._request_json(object()) == {"ok": True}
    assert calls == 2
