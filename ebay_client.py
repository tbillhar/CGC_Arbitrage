"""eBay Browse API client.

The client is intentionally small: it performs real Browse API requests when
credentials are available, and raises typed errors when scanning cannot proceed.
"""

from __future__ import annotations

import base64
import csv
import json
import ssl
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi
import truststore

from config import EBAY, EbayConfig


@dataclass(frozen=True)
class EbayListing:
    item_id: str
    title: str
    price: float
    currency: str
    item_url: str
    seller_username: str


class EbayCredentialsMissingError(RuntimeError):
    pass


class EbayApiError(RuntimeError):
    pass


class EbayAuthError(EbayApiError):
    pass


class EbayClient:
    def __init__(self, config: EbayConfig = EBAY) -> None:
        self.config = config
        self._access_token: str | None = None
        self._ssl_context = self._create_ssl_context()

    @property
    def has_credentials(self) -> bool:
        return bool(self.config.client_id and self.config.client_secret)

    @property
    def is_mock_mode(self) -> bool:
        return self.config.mode == "mock"

    def search_active_listings(
        self,
        title: str,
        issue_number: str,
        min_grade: float,
        max_grade: float,
        limit: int = 50,
    ) -> list[EbayListing]:
        if self.is_mock_mode:
            return self._search_mock_listings(title, issue_number, limit)

        if not self.has_credentials:
            raise EbayCredentialsMissingError("eBay credentials are not configured.")

        query = f'{title} #{issue_number} CGC {min_grade:g} {max_grade:g}'
        params = urlencode({"q": query, "limit": str(limit), "filter": "buyingOptions:{FIXED_PRICE|AUCTION}"})
        try:
            payload = self._get_json(f"{self.config.browse_base_url}/item_summary/search?{params}")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise EbayApiError(f"eBay Browse API request failed: {error}") from error
        return list(self._parse_item_summaries(payload.get("itemSummaries", [])))

    def _search_mock_listings(self, title: str, issue_number: str, limit: int) -> list[EbayListing]:
        if not self.config.mock_listings_path.exists():
            raise EbayApiError(f"Mock eBay listings file not found: {self.config.mock_listings_path}")

        matches: list[EbayListing] = []
        title_key = title.strip().casefold()
        issue_key = issue_number.strip().casefold()
        with self.config.mock_listings_path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            required_columns = {"item_id", "watch_title", "watch_issue_number", "title", "price", "item_url"}
            if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
                missing = ", ".join(sorted(required_columns - set(reader.fieldnames or [])))
                raise EbayApiError(f"Mock eBay listings file is missing required columns: {missing}")

            for line_number, row in enumerate(reader, start=2):
                if (row["watch_title"].strip().casefold(), row["watch_issue_number"].strip().casefold()) != (
                    title_key,
                    issue_key,
                ):
                    continue
                try:
                    price = float(row["price"])
                except (TypeError, ValueError) as error:
                    raise EbayApiError(f"Mock eBay listings row {line_number} has an invalid price.") from error

                matches.append(
                    EbayListing(
                        item_id=row["item_id"].strip(),
                        title=row["title"].strip(),
                        price=price,
                        currency=(row.get("currency") or "USD").strip() or "USD",
                        item_url=row["item_url"].strip(),
                        seller_username=(row.get("seller_username") or "mock_seller").strip(),
                    )
                )
                if len(matches) >= limit:
                    break

        return matches

    def _parse_item_summaries(self, items: Iterable[dict[str, Any]]) -> Iterable[EbayListing]:
        for item in items:
            price_value, currency = self._item_price(item)
            seller = item.get("seller") or {}

            yield EbayListing(
                item_id=str(item.get("itemId", "")),
                title=str(item.get("title", "")),
                price=price_value,
                currency=currency,
                item_url=str(item.get("itemWebUrl", "")),
                seller_username=str(seller.get("username", "")),
            )

    def _item_price(self, item: dict[str, Any]) -> tuple[float, str]:
        for field_name in ("price", "currentBidPrice", "minimumPriceToBid"):
            price = item.get(field_name) or {}
            try:
                value = float(price.get("value", 0))
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                return value, str(price.get("currency", "USD"))
        return 0.0, "USD"

    def _get_json(self, url: str) -> dict[str, Any]:
        token = self._access_token or self._fetch_access_token()
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self.config.marketplace_id,
                "Accept": "application/json",
            },
        )
        try:
            return self._request_json(request)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            raise EbayApiError(f"eBay Browse API request failed: {error}") from error

    def _fetch_access_token(self) -> str:
        credentials = f"{self.config.client_id}:{self.config.client_secret}".encode("utf-8")
        request = Request(
            self.config.oauth_token_url,
            data=b"grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope",
            headers={
                "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            payload = self._request_json(request)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            raise EbayAuthError(
                "eBay OAuth request failed. Check that EBAY_CLIENT_ID and "
                "EBAY_CLIENT_SECRET are from the same eBay environment as the "
                "configured OAuth/Browse URLs, and that there are no extra "
                "spaces or quotes in the environment variables. "
                f"Underlying error: {error}"
            ) from error
        self._access_token = str(payload["access_token"])
        return self._access_token

    def _request_json(self, request: Request, attempts: int = 3) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                with urlopen(request, timeout=20, context=self._ssl_context) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError:
                raise
            except (URLError, TimeoutError, OSError) as error:
                last_error = error
                if attempt == attempts - 1:
                    break
                time.sleep(0.5 * (attempt + 1))
        raise last_error or EbayApiError("eBay request failed without an error.")

    def _create_ssl_context(self) -> ssl.SSLContext:
        try:
            return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except Exception:
            return ssl.create_default_context(cafile=certifi.where())
