"""eBay Browse API client.

The client is intentionally small: it performs real Browse API requests when
credentials are available, and raises typed errors when scanning cannot proceed.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


class EbayClient:
    def __init__(self, config: EbayConfig = EBAY) -> None:
        self.config = config
        self._access_token: str | None = None

    @property
    def has_credentials(self) -> bool:
        return bool(self.config.client_id and self.config.client_secret)

    def search_active_listings(
        self,
        title: str,
        issue_number: str,
        min_grade: float,
        max_grade: float,
        limit: int = 50,
    ) -> list[EbayListing]:
        if not self.has_credentials:
            raise EbayCredentialsMissingError("eBay credentials are not configured.")

        query = f'{title} #{issue_number} CGC {min_grade:g} {max_grade:g}'
        params = urlencode({"q": query, "limit": str(limit), "filter": "buyingOptions:{FIXED_PRICE|AUCTION}"})
        try:
            payload = self._get_json(f"{self.config.browse_base_url}/item_summary/search?{params}")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise EbayApiError(f"eBay Browse API request failed: {error}") from error
        return list(self._parse_item_summaries(payload.get("itemSummaries", [])))

    def _parse_item_summaries(self, items: Iterable[dict[str, Any]]) -> Iterable[EbayListing]:
        for item in items:
            price = item.get("price") or {}
            seller = item.get("seller") or {}
            try:
                value = float(price.get("value", 0))
            except (TypeError, ValueError):
                value = 0.0

            yield EbayListing(
                item_id=str(item.get("itemId", "")),
                title=str(item.get("title", "")),
                price=value,
                currency=str(price.get("currency", "USD")),
                item_url=str(item.get("itemWebUrl", "")),
                seller_username=str(seller.get("username", "")),
            )

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
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
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
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise EbayApiError(f"eBay OAuth request failed: {error}") from error
        self._access_token = str(payload["access_token"])
        return self._access_token
